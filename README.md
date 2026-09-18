# GridWise LLM — BUP CSE Fest 2026 Preliminary

Public HTTP API that interprets campus operator notes (Gemini Flash + validated fallback) and returns a cost-optimal 24-hour energy schedule.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"status":"ok"}` |
| `POST` | `/optimize-energy` | Interpret notes + optimize schedule |

## Quick start (local)

```bash
cd gridwise-llm
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt

# Free key: https://aistudio.google.com/apikey
copy .env.example .env
# edit .env and set GEMINI_API_KEY=...

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Without `GEMINI_API_KEY`, the service still runs using a deterministic heuristic interpreter (good for local smoke tests). **For the contest, set a Gemini key** so the LLM is on the interpretation path.

## Deploy (Render) — required for submission

1. Get a **free** Gemini key: https://aistudio.google.com/apikey
2. Push this folder to GitHub (new public/private repo).
3. On [Render](https://dashboard.render.com) → **New → Web Service** → connect the repo.
4. Settings:
   - **Runtime**: Python 3
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Env**: `GEMINI_API_KEY=<your key>`, `GEMINI_MODEL=gemini-2.0-flash`
5. After deploy, open `https://YOUR-SERVICE.onrender.com/health` → `{"status":"ok"}`
6. Submit that base URL in the fest portal (Participant Guide).

Cold starts on free Render can take ~30–60s; hit `/health` once before judges run.

## Test sample pack

Save the official JSON as:

`samples/GridWise_Public_LLM_Sample_Case_Pack_v2.json`

Then:

```bash
python tests/test_heuristic.py
python tests/run_sample_pack.py
```

## Architecture

1. **LLM / heuristic** → structured directives  
2. **Guardrails** → whitelist + normalize hours/values  
3. **PuLP CBC** → minimize `Σ grid[h] * tariff[h]`  
4. **Replay validator** → energy balance, battery, directives, EOD neutrality  

## Env vars

| Var | Required | Default |
|-----|----------|---------|
| `GEMINI_API_KEY` | for contest | — |
| `GEMINI_MODEL` | no | `gemini-2.0-flash` |
| `PORT` | no | `8000` |
