"""Bill extraction with Gemini vision.

Reads a downloaded bill (JPG/PNG photo or PDF, including scanned/image-only
PDFs) directly with Gemini's multimodal model — no OCR, no pytesseract.
Returns the Bill JSON the engine's /audit expects (shape from engine/main.py,
per CONTRACT.md).

If the file can't be read, or the fields needed for the audit are unreadable,
ExtractionError carries a friendly, user-facing message saying what was
unreadable. No key is ever printed or logged.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

log = logging.getLogger("truebill.extractor")

# Repo root: <TrueBill-repo>/bot/this_file.py -> <TrueBill-repo>/.env
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

# Same vision model the engine's explain.py uses.
MODEL = "gemini-3.8-flash"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

# Gemini inline data (base64 in the request) is capped around 20 MB;
# stay under it so every accepted file actually fits in one request.
MAX_FILE_BYTES = 19 * 1024 * 1024

GEMINI_TIMEOUT_MS = 90_000

# Fields the audit cannot run without; missing ones produce a friendly error.
REQUIRED_FIELD_LABELS = {
    "units_consumed": "units consumed",
    "sanctioned_load_kw": "sanctioned load (kW)",
    "energy": "energy charge",
    "fixed": "fixed charge",
    "surcharges": "surcharges",
}

PROMPT = """\
You are reading an electricity bill for a household bill-audit bot
(discom BSES Rajdhani / BRPL, Delhi; category Domestic).

Look at the attached bill (a photo or a PDF page) and extract the details.

STRICT RULES:
- Copy every number exactly as printed on the bill. Never calculate,
  correct, or guess a value.
- If a value is not printed, or you cannot read it clearly, use null and
  add its key to "missing_fields". Never invent values.
- Dates are "YYYY-MM-DD". billing_period is the period the bill covers.
- discom: one of "BRPL", "TATA", "NDPL" if you can identify it, else null.
- category: exactly as printed (for example "Domestic"), else null.
- charges.surcharges is the TOTAL of all surcharge / duty / cess / fuel
  adjustment lines combined (not one line separately).
- charges.total is the final amount payable.
- If this is not an electricity bill at all, return an empty object {}.

Reply with ONLY a JSON object in exactly this shape:
{
  "discom": "BRPL",
  "category": "Domestic",
  "consumer_name": "string or null",
  "billing_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or null,
  "units_consumed": number or null,
  "sanctioned_load_kw": number or null,
  "charges": {
    "energy": number or null,
    "fixed": number or null,
    "surcharges": number or null,
    "other": number or null,
    "total": number or null
  },
  "missing_fields": ["keys you could not read"]
}"""


class ExtractionError(Exception):
    """A user-facing problem reading the bill; the message is safe to show."""


def _number(value) -> float | None:
    """Coerce a Gemini value (number or '1,234.50'-style string) to float."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("₹", "").replace("Rs.", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _clean_text(value) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _parse_json(text: str) -> dict:
    """Parse Gemini's reply, tolerating accidental ```json fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = text.strip()
    if fenced.startswith("```"):
        fenced = fenced.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        raise ExtractionError(
            "I couldn't read this file as an electricity bill. Please send a "
            "clearer photo or a sharper scan of the bill."
        )


def _call_gemini(data: bytes, mime_type: str) -> dict:
    """Send the file to Gemini vision and return its parsed JSON reply."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        # Print the key name only, never its value.
        raise ExtractionError(
            "GEMINI_API_KEY isn't configured on the server. Please ask the "
            "admin to add it to the .env file."
        )

    try:
        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": GEMINI_TIMEOUT_MS},
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                PROMPT,
            ],
            config={"response_mime_type": "application/json"},
        )
    except Exception as exc:  # API/network/key problems -> friendly message
        log.warning("Gemini vision call failed: %s", type(exc).__name__)
        raise ExtractionError(
            "I couldn't read the bill because the vision service is "
            "unavailable right now. Please try again in a few minutes — if "
            "it keeps happening, let the admin know."
        )

    reply = response.text
    if not reply:
        raise ExtractionError(
            "I couldn't read this file as an electricity bill — the image may "
            "be too blurry, too dark, or cut off. Please send a clearer "
            "photo or scan."
        )
    return _parse_json(reply)


def _normalize_bill(raw: dict) -> dict:
    """Shape Gemini's reply into the Bill JSON the engine's /audit accepts."""
    charges = raw.get("charges") if isinstance(raw.get("charges"), dict) else {}
    period = raw.get("billing_period") if isinstance(raw.get("billing_period"), dict) else None

    billing_period = None
    if period:
        start = _clean_text(period.get("start"))
        end = _clean_text(period.get("end"))
        if start and end:
            billing_period = {"start": start, "end": end}

    bill = {
        "discom": _clean_text(raw.get("discom")) or "BRPL",
        "category": _clean_text(raw.get("category")) or "Domestic",
        "consumer_name": _clean_text(raw.get("consumer_name")),
        "billing_period": billing_period,
        "units_consumed": _number(raw.get("units_consumed")),
        "sanctioned_load_kw": _number(raw.get("sanctioned_load_kw")),
        "charges": {
            "energy": _number(charges.get("energy")),
            "fixed": _number(charges.get("fixed")),
            "surcharges": _number(charges.get("surcharges")),
            "other": _number(charges.get("other")),
            "total": _number(charges.get("total")),
        },
        "missing_fields": [],
    }

    # What Gemini said it couldn't read, plus what we found unreadable.
    reported = raw.get("missing_fields")
    missing = set(reported) if isinstance(reported, list) else set()
    if bill["units_consumed"] is None:
        missing.add("units_consumed")
    if bill["sanctioned_load_kw"] is None:
        missing.add("sanctioned_load_kw")
    for key in ("energy", "fixed", "surcharges"):
        if bill["charges"][key] is None:
            missing.add(key)
    bill["missing_fields"] = sorted(missing)
    return bill


def extract_bill(file_path: str | Path) -> dict:
    """Read a bill file (JPG/PNG photo or PDF) and return its Bill JSON.

    Uses Gemini vision — works on photos, text PDFs, and scanned PDFs alike.
    `sanctioned_load_kw` is always present (None if unreadable).
    Raises ExtractionError with a friendly message when the bill can't be
    read or the fields the audit needs are missing.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ExtractionError(
            "The downloaded file is missing. Please send the bill again."
        )

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(
            "That file type isn't supported. Please send a JPG, PNG, or PDF "
            "of the bill."
        )

    if path.stat().st_size > MAX_FILE_BYTES:
        raise ExtractionError(
            "That file is too large (over 19 MB). Please send a smaller "
            "photo or PDF of the bill."
        )

    raw = _call_gemini(path.read_bytes(), MIME_BY_EXTENSION[suffix])
    if not raw:
        raise ExtractionError(
            "This doesn't look like an electricity bill, so there's nothing "
            "to audit. Please send a photo or PDF of your BRPL bill."
        )

    bill = _normalize_bill(raw)

    # Fields the audit cannot run without -> say exactly what was unreadable.
    unreadable = [
        REQUIRED_FIELD_LABELS[key]
        for key in REQUIRED_FIELD_LABELS
        if key in bill["missing_fields"]
    ]
    if unreadable:
        raise ExtractionError(
            "I could open the file but couldn't read these parts of the "
            f"bill: {', '.join(unreadable)}. Please send a clearer photo or "
            "a sharper scan — good lighting, with the whole bill in frame."
        )

    return bill
