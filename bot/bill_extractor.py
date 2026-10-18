"""Extract BRPL domestic bill data from an image or PDF using Gemini vision."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError


ENV_PATH = Path(r"C:\Users\user\Desktop\TrueBill-repo\.env")
GEMINI_MODEL = "gemini-3.8-flash"


class _StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class BillingPeriod(_StrictModel):
    start: str | None = Field(...)
    end: str | None = Field(...)


class Charges(_StrictModel):
    energy: float | None = Field(...)
    fixed: float | None = Field(...)
    surcharges: float | None = Field(...)
    other: float | None = Field(...)
    total: float | None = Field(...)


class Bill(_StrictModel):
    """The Bill JSON shape accepted by the TrueBill API."""

    discom: str
    category: str
    consumer_name: str | None = Field(...)
    billing_period: BillingPeriod
    units_consumed: float | None = Field(...)
    sanctioned_load_kw: float | None = Field(...)
    charges: Charges
    missing_fields: list[str]


def _bill_schema() -> dict[str, Any]:
    if hasattr(Bill, "model_json_schema"):
        return Bill.model_json_schema()
    return Bill.schema()


def _validate_bill(data: dict[str, Any]) -> dict[str, Any]:
    if hasattr(Bill, "model_validate"):
        return Bill.model_validate(data).model_dump()
    return Bill.parse_obj(data).dict()


def _mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None or not (
        mime_type.startswith("image/") or mime_type == "application/pdf"
    ):
        raise ValueError(f"Expected an image or PDF file, got {path.suffix or '(none)'}.")
    return mime_type


def _validate_dates(result: dict[str, Any]) -> None:
    for field in ("start", "end"):
        value = result["billing_period"][field]
        if value is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError(f"billing_period.{field} must use YYYY-MM-DD.")
            date.fromisoformat(value)


def _null_paths(value: Any, path: str = "") -> list[str]:
    missing: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "missing_fields":
                continue
            child_path = f"{path}.{key}" if path else key
            missing.extend(_null_paths(child, child_path))
    elif value is None:
        missing.append(path)
    return missing


def _parse_and_validate(response_text: str) -> dict[str, Any]:
    data = json.loads(response_text)
    if not isinstance(data, dict):
        raise ValueError("Gemini response must be one JSON object.")
    # These identify the requested extraction class and are fixed by the task.
    data["discom"] = "BRPL"
    data["category"] = "Domestic"
    data.setdefault("missing_fields", [])
    result = _validate_bill(data)
    _validate_dates(result)
    result["missing_fields"] = list(
        dict.fromkeys([*result["missing_fields"], *_null_paths(result)])
    )
    return result


def extract_bill(file_path: str | Path) -> dict[str, Any]:
    """Return validated BRPL Domestic bill JSON fields extracted from a file.

    The result contains exactly the Bill JSON keys: discom, category,
    consumer_name, billing_period, units_consumed, sanctioned_load_kw,
    charges, and missing_fields.
    """
    path = Path(file_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("file_path must point to a regular file.")
    mime_type = _mime_type(path)

    load_dotenv(ENV_PATH, override=True)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY is not set in {ENV_PATH}.")

    file_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
    schema = json.dumps(_bill_schema(), ensure_ascii=False)
    prompt = f"""Read this BSES Rajdhani Power Limited (BRPL) Domestic electricity bill.
Return one JSON object only, with exactly this schema and no markdown or extra
keys:
{schema}

Extract only values supported by the visible bill; never guess. Use null for
any unreadable or absent value. Keep billing_period as an object with start
and end dates in YYYY-MM-DD format, and charges as an object with energy,
fixed, surcharges, other, and total amounts. Use JSON numbers for numeric
values. Put every unreadable field's dotted path (for example,
"charges.energy" or "billing_period.start") in missing_fields. Set discom to
"BRPL" and category to "Domestic"."""

    repair_context = ""
    with genai.Client(api_key=api_key) as client:
        for attempt in range(2):
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, repair_context, file_part]
                if repair_context
                else [prompt, file_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            response_text = response.text or ""
            try:
                return _parse_and_validate(response_text)
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                if attempt == 1:
                    raise ValueError(
                        "Gemini returned invalid bill JSON after one retry."
                    ) from exc
                repair_context = (
                    "Your previous response was invalid JSON or failed validation. "
                    "Correct it to match the schema exactly. Validation error: "
                    + str(exc)
                    + "\nPrevious response:\n"
                    + response_text
                )
    raise RuntimeError("Gemini did not return a bill response.")


__all__ = ["extract_bill"]
