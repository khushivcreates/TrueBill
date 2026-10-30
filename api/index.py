"""Serverless API used by the Vite application on Vercel."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot"))
sys.path.insert(0, str(ROOT / "engine"))

from bill_extractor import ExtractionError, SUPPORTED_EXTENSIONS, extract_bill  # noqa: E402
from engine import audit  # noqa: E402
from explain import explain  # noqa: E402

TARIFF_PATH = ROOT / "retrieval" / "tariff_cache" / "brpl_domestic.json"

app = FastAPI(title="TrueBill API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def load_tariff() -> dict:
    try:
        return json.loads(TARIFF_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("The verified tariff data is unavailable.") from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/process")
async def process(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "Send a JPG, PNG, or PDF electricity bill.")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "The uploaded file is empty.")

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        try:
            bill = extract_bill(temporary_path)
        finally:
            temporary_path.unlink(missing_ok=True)

        tariff = load_tariff()
        result = audit(bill, tariff)
        extra = explain(result, bill, tariff)
        result.update(extra)
        result["sources"] = [{
            "title": f"{tariff['discom']} {tariff['category']} tariff",
            "url": tariff["source_url"],
            "effective_date": tariff["effective_date"],
        }]
        return result
    except ExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        raise HTTPException(500, "The bill could not be audited. Please try again later.")
