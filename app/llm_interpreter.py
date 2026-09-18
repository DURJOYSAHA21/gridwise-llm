from __future__ import annotations

import json
import os
import re
from typing import Any

from app.guardrails import validate_and_normalize_directives

SYSTEM_PROMPT = """You extract GridWise campus energy operator directives from natural-language notes.

Return ONLY a JSON array with exactly one object per operator note, in note_index order (0..N-1).
No markdown fences. No extra keys outside the schema.

Each object:
{
  "note_index": <int>,
  "applies": <bool>,
  "directive_type": "solar_reduction" | "minimum_battery_reserve" | "no_charge_window" | "no_discharge_window" | "max_grid_window" | "no_op",
  "structured_adjustment": <object or null>,
  "explanation": <short string>
}

Rules:
1. Time windows are start-inclusive and end-exclusive on whole hours.
   "1 PM to 3 PM" / "13:00-15:00" / "from noon until 2 PM" => hours [12,13] for noon-2PM; [13,14] for 1-3PM.
   "2 AM until 5 AM" => [2,3,4]. "6 PM until 9 PM" => [18,19,20]. "6 PM until 10 PM" => [18,19,20,21].
2. solar_reduction.factor is the USABLE FRACTION remaining (0..1).
   "drop to 25%" / "25% of forecast" => factor 0.25.
   "about half" / "50%" remaining => factor 0.5.
   "80% reduction" => factor 0.2 (NOT 0.8).
3. minimum_battery_reserve needs absolute kWh.
   If note says "50% of battery capacity" and capacity_kwh is provided, convert: 0.5 * capacity.
4. no_charge_window / no_discharge_window: structured_adjustment = {"hours":[...]} only.
5. max_grid_window: {"hours":[...], "max_grid_kwh": number}.
6. Irrelevant notes (menus, deadlines, library hours, seminars, sports, student affairs) => no_op with applies=false and structured_adjustment=null.
7. For every non-no_op: applies=true. For no_op: applies=false and structured_adjustment=null.
8. hours must be unique integers 0..23 ascending.
9. Do not invent demand/tariff/battery parameter changes beyond these directive types.
"""


def interpret_notes(
    operator_notes: list[str],
    battery_capacity_kwh: float,
) -> list[dict[str, Any]]:
    raw = _call_llm(operator_notes, battery_capacity_kwh)
    if raw is None:
        raw = _heuristic_interpret(operator_notes, battery_capacity_kwh)
    return validate_and_normalize_directives(raw, len(operator_notes), battery_capacity_kwh)


def _call_llm(notes: list[str], capacity: float) -> list[dict[str, Any]] | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    user_payload = {
        "battery_capacity_kwh": capacity,
        "operator_notes": [{"note_index": i, "text": n} for i, n in enumerate(notes)],
    }
    prompt = (
        SYSTEM_PROMPT
        + "\n\nBattery capacity for percentage conversion: "
        + str(capacity)
        + " kWh\n\nNotes JSON:\n"
        + json.dumps(user_payload, indent=2)
        + "\n\nReturn the JSON array now."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        text = (response.text or "").strip()
        return _parse_json_array(text)
    except Exception:
        # One retry with fallback model name
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            return _parse_json_array((response.text or "").strip())
        except Exception:
            return None


def _parse_json_array(text: str) -> list[dict[str, Any]] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict) and "directive_interpretation" in data:
        data = data["directive_interpretation"]
    if not isinstance(data, list):
        return None
    return data


# --- Heuristic fallback (used when no API key / LLM failure); still validated by guardrails ---

_TIME_PATTERNS = [
    # from X until Y / between X and Y / from X to Y
    re.compile(
        r"(?:from|between|during)?\s*"
        r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?|noon|midnight)\s*"
        r"(?:until|to|and|-|–|—)\s*"
        r"(?P<end>\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?|noon|midnight)",
        re.I,
    ),
]


def _parse_hour_token(tok: str) -> int | None:
    tok = tok.strip().lower()
    if tok == "noon":
        return 12
    if tok == "midnight":
        return 0
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", tok, re.I)
    if not m:
        return None
    h = int(m.group(1))
    mins = int(m.group(2) or 0)
    ap = (m.group(3) or "").lower()
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not ap and h > 23:
        return None
    # If minutes > 0, still use the hour as start; end exclusivity handled by range
    if h < 0 or h > 23:
        return None
    if mins > 0:
        # treat :30 as still that clock hour for start; for end, round up conceptually
        # Sample uses whole hours only; ignore minutes.
        pass
    return h


def _extract_hours(text: str) -> list[int] | None:
    for pat in _TIME_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        start = _parse_hour_token(m.group("start"))
        end = _parse_hour_token(m.group("end"))
        if start is None or end is None:
            continue
        if end == start:
            return None
        if end > start:
            hours = list(range(start, end))
        else:
            # wrap (unlikely in samples)
            hours = list(range(start, 24)) + list(range(0, end))
        return hours
    return None


def _heuristic_interpret(notes: list[str], capacity: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, note in enumerate(notes):
        out.append(_heuristic_one(i, note, capacity))
    return out


def _heuristic_one(idx: int, note: str, capacity: float) -> dict[str, Any]:
    text = note.strip()
    low = text.lower()

    distractor_kw = [
        "menu",
        "cafeteria",
        "registration deadline",
        "library",
        "book-return",
        "book return",
        "student affairs",
        "club notices",
        "seminar room",
        "sports office",
        "next week",
        "next month",
        "tomorrow",
    ]
    energy_kw = [
        "solar",
        "battery",
        "charge",
        "discharge",
        "grid",
        "feeder",
        "transformer",
        "substation",
        "reserve",
        "pv",
        "panel",
        "inverter",
        "kwh",
        "import",
    ]

    if any(k in low for k in distractor_kw) and not any(k in low for k in energy_kw):
        return {
            "note_index": idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note does not affect today's energy schedule.",
        }

    hours = _extract_hours(text)

    # solar reduction
    if any(k in low for k in ["solar", "pv", "panel", "rooftop"]) and any(
        k in low for k in ["reduction", "reduce", "drop", "washing", "wash", "cleaning", "cloud", "inspection", "inverter"]
    ):
        factor = None
        # "80% reduction"
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*reduction", low)
        if m:
            factor = 1.0 - float(m.group(1)) / 100.0
        # "drop to about 20%" / "treated as roughly 25%" / "leave about half"
        if factor is None:
            m = re.search(
                r"(?:drop to|treated as|leave|left as|remain(?:ing)?|usable(?:\s+solar)?(?:\s+should be)?|about|roughly|approximately)?\s*"
                r"(?:as\s+)?(?:roughly\s+|about\s+|approximately\s+)?"
                r"(\d+(?:\.\d+)?)\s*%",
                low,
            )
            if m and "reduction" not in low[max(0, m.start() - 20) : m.end()]:
                # percent remaining if phrased as "X% of forecast" or "drop to X%"
                pct = float(m.group(1)) / 100.0
                if "reduction" in low:
                    factor = 1.0 - pct
                elif any(p in low for p in ["drop to", "treated as", "of the forecast", "of forecast", "usable"]):
                    factor = pct
                elif "half" in low:
                    factor = 0.5
                else:
                    # ambiguous percent near solar — if "reduction" elsewhere handled; else remaining
                    factor = pct
        if "half" in low and factor is None:
            factor = 0.5
        if "one-fifth" in low or "one fifth" in low:
            factor = 0.2
        if factor is not None and hours:
            factor = max(0.0, min(1.0, factor))
            return {
                "note_index": idx,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": hours, "factor": factor},
                "explanation": "Solar availability reduced for the stated window.",
            }

    # no charge
    if (
        ("charge" in low and any(k in low for k in ["not", "no ", "disabled", "unavailable", "isolated", "do not"]))
        or "charging circuit" in low
        or "charger will be" in low
        or "charging is disabled" in low
        or "battery charger" in low
    ) and "discharge" not in low:
        if hours:
            return {
                "note_index": idx,
                "applies": True,
                "directive_type": "no_charge_window",
                "structured_adjustment": {"hours": hours},
                "explanation": "Battery charging unavailable during the stated window.",
            }

    # no discharge
    if ("discharge" in low and any(k in low for k in ["not", "no ", "disabled", "do not", "must not"])) or (
        "relay testing" in low and "discharge" in low
    ):
        if hours:
            return {
                "note_index": idx,
                "applies": True,
                "directive_type": "no_discharge_window",
                "structured_adjustment": {"hours": hours},
                "explanation": "Battery discharge disabled during the stated window.",
            }

    # reserve
    if any(k in low for k in ["reserve", "keep at least", "remain in the battery", "stored in the battery"]):
        reserve = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(?:the\s+)?battery", low)
        if m:
            reserve = float(m.group(1)) / 100.0 * capacity
        if reserve is None:
            m = re.search(r"(?:at least|keep|require(?:s)?)\s*(\d+(?:\.\d+)?)\s*kwh", low)
            if m:
                reserve = float(m.group(1))
        if reserve is None:
            m = re.search(r"(\d+(?:\.\d+)?)\s*kwh", low)
            if m:
                reserve = float(m.group(1))
        if reserve is not None and hours:
            return {
                "note_index": idx,
                "applies": True,
                "directive_type": "minimum_battery_reserve",
                "structured_adjustment": {"hours": hours, "minimum_energy_kwh": reserve},
                "explanation": "Minimum battery reserve applied for the stated window.",
            }

    # max grid
    if any(k in low for k in ["grid", "feeder", "transformer", "substation", "import", "intake"]) and any(
        k in low for k in ["not exceed", "must not exceed", "at or below", "cap", "limit", "constrained"]
    ):
        m = re.search(r"(\d+(?:\.\d+)?)\s*kwh", low)
        if m and hours:
            return {
                "note_index": idx,
                "applies": True,
                "directive_type": "max_grid_window",
                "structured_adjustment": {"hours": hours, "max_grid_kwh": float(m.group(1))},
                "explanation": "Grid import capped during the stated window.",
            }

    # fallback distractor / unknown
    if not any(k in low for k in energy_kw):
        return {
            "note_index": idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "This note does not affect today's energy schedule.",
        }

    return {
        "note_index": idx,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": "Could not map note to a supported directive; treated as no_op.",
    }
