"""Vercel serverless entrypoint for the FastAPI app."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mangum import Mangum

from app.main import app

# AWS Lambda-style handler used by Vercel Python for ASGI apps
handler = Mangum(app, lifespan="off")
