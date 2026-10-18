"""Real bill processing pipeline.

extract_bill() (Gemini vision: JPG/PNG/PDF incl. scans) -> cached BRPL
tariff (read-only) -> engine POST /audit -> Audit JSON.

Any failure (unreadable bill, broken cache, API down) returns a friendly
error dict instead of raising, so the bot can tell the user what went wrong.
No key is ever printed or logged.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from bill_extractor import SUPPORTED_EXTENSIONS, ExtractionError, extract_bill

log = logging.getLogger("truebill.processor")

# Repo root: <TrueBill-repo>/bot/this_file.py -> <TrueBill-repo>/.env
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

# Read-only tariff cache produced by the retrieval step. Never written here.
TARIFF_CACHE_PATH = REPO_ROOT / "retrieval" / "tariff_cache" / "brpl_domestic.json"

AUDIT_TIMEOUT_SECONDS = 60.0

ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS  # .jpg, .jpeg, .png, .pdf


def is_supported(file_path: str | Path) -> bool:
    """True when the file is a supported bill: JPG, PNG, or PDF."""
    return Path(file_path).suffix.lower() in ALLOWED_EXTENSIONS


def _error(message: str) -> dict:
    """Audit-shaped dict carrying a friendly error message for the user."""
    return {
        "error": message,
        "checks": [],
        "explanation": "",
        "sources": [],
        "uncertainties": [],
        "draft_complaint": "",
    }


def load_tariff() -> dict:
    """Load the cached BRPL domestic tariff. Opens the file read-only."""
    try:
        with open(TARIFF_CACHE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise ExtractionError(
            "The BRPL tariff cache is missing on the server "
            "(retrieval/tariff_cache/brpl_domestic.json). Please run the "
            "tariff retrieval step first."
        )
    except json.JSONDecodeError:
        raise ExtractionError(
            "The BRPL tariff cache is corrupted and can't be read. Please "
            "re-run the tariff retrieval step to refresh it."
        )


def call_audit_api(bill: dict, tariff: dict, api_url: str) -> dict:
    """POST {bill, tariff} to the engine's /audit and return its Audit JSON."""
    try:
        response = httpx.post(
            api_url,
            json={"bill": bill, "tariff": tariff},
            timeout=AUDIT_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise ExtractionError(
            f"The audit service didn't answer within "
            f"{int(AUDIT_TIMEOUT_SECONDS)} seconds. Please try again in a bit."
        )
    except httpx.HTTPError:
        raise ExtractionError(
            "I couldn't reach the audit service. Please try again in a few "
            "minutes — if it keeps happening, let the admin know."
        )

    if response.status_code != 200:
        log.warning("Audit API returned HTTP %s", response.status_code)
        raise ExtractionError(
            f"The audit service replied with an error (HTTP "
            f"{response.status_code}). Please try again later."
        )

    try:
        audit = response.json()
    except ValueError:
        raise ExtractionError(
            "The audit service returned something that wasn't valid JSON. "
            "Please try again later."
        )

    if not isinstance(audit, dict):
        raise ExtractionError(
            "The audit service returned an unexpected response. Please try "
            "again later."
        )
    return audit


def process_bill(file_path: str | Path) -> dict:
    """Process a downloaded bill file and return the engine's Audit JSON.

    On failure, returns a dict with an `error` key holding a friendly,
    user-facing message (never raises to the caller).
    """
    try:
        log.info("extracting bill")
        bill = extract_bill(file_path)
        tariff = load_tariff()

        api_url = os.getenv("AUDIT_API_URL", "").strip()
        if not api_url:
            raise ExtractionError(
                "AUDIT_API_URL isn't configured on the server. Please ask "
                "the admin to add it to the .env file."
            )

        log.info("calling audit API")
        audit = call_audit_api(bill, tariff, api_url)
        log.info("audit received")
        return audit
    except ExtractionError as exc:
        # Friendly, already user-facing message from the pipeline.
        return _error(str(exc))
    except Exception:
        # Unexpected bug: log the traceback (contains no keys), tell the user
        # something generic but honest.
        log.exception("Unexpected failure while processing a bill")
        return _error(
            "Something unexpected went wrong while auditing this bill. "
            "Please try again — if it keeps happening, let the admin know."
        )
