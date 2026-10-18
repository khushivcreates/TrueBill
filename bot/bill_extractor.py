"""Vision-based BRPL domestic bill extraction using Gemini."""

from __future__ import annotations

import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError


ENV_PATH = Path(r"C:\Users\user\Desktop\TrueBill-repo\.env")
GEMINI_MODEL = "gemini-3.8-flash"


class _StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class EnergySlab(_StrictModel):
    from_units: int | None = Field(...)
    to_units: int | None = Field(...)
    rate_per_unit: float | None = Field(...)


class FixedCharge(_StrictModel):
    from_kw: float | None = Field(...)
    to_kw: float | None = Field(...)
    rate_per_kw_per_month: float | None = Field(...)


class Surcharge(_StrictModel):
    name: str | None = Field(...)
    type: Literal["percent_of_energy_plus_fixed"] | None = Field(...)
    value: float | None = Field(...)
    effective_date: str | None = Field(...)


class FppasMonth(_StrictModel):
    month: str | None = Field(...)
    percent: float | None = Field(...)
    source_url: str | None = Field(...)


class OtherSource(_StrictModel):
    component: str | None = Field(...)
    url: str | None = Field(...)


class Bill(_StrictModel):
    """Contract Bill JSON fields plus missing_fields, which the API accepts."""

    discom: str
    category: str
    effective_date: str | None = Field(...)
    energy_slabs: list[EnergySlab] | None = Field(...)
    fixed_charge: list[FixedCharge] | None = Field(...)
    surcharges: list[Surcharge] | None = Field(...)
    fppas_by_month: list[FppasMonth] | None = Field(...)
    source_url: str | None = Field(...)
    other_sources: list[OtherSource] | None = Field(...)
    uncertainties: list[str]
    retrieved_at: str
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
    if mime_type is None:
        raise ValueError(f"Unsupported or unrecognized file type: {path.suffix or '(none)'}")
    if not (mime_type.startswith("image/") or mime_type == "application/pdf"):
        raise ValueError(f"Gemini vision input must be an image or PDF, got {mime_type}.")
    return mime_type


def _missing_paths(value: Any, path: str = "") -> list[str]:
    """Return JSON paths for null values so none are omitted from missing_fields."""
    missing: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"missing_fields", "uncertainties"}:
                continue
            child_path = f"{path}.{key}" if path else key
            missing.extend(_missing_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            missing.extend(_missing_paths(child, f"{path}[{index}]"))
    elif value is None:
        missing.append(path)
    return missing


def _parse_and_validate(response_text: str, retrieved_at: str) -> dict[str, Any]:
    data = json.loads(response_text)
    if not isinstance(data, dict):
        raise ValueError("Gemini response must be one JSON object.")

    # These values identify the requested bill class and are not inferred from
    # potentially blurry print on the document.
    data["discom"] = "BRPL"
    data["category"] = "Domestic"
    data["retrieved_at"] = retrieved_at
    data.setdefault("uncertainties", [])
    data.setdefault("missing_fields", [])
    result = _validate_bill(data)

    null_paths = _missing_paths(result)
    result["missing_fields"] = list(
        dict.fromkeys([*result["missing_fields"], *null_paths])
    )
    return result


def extract_bill(file_path: str | Path) -> dict[str, Any]:
    """Extract BRPL Domestic bill data, validate it, and retry once if invalid.

    The local file is sent to Gemini as image/PDF input. The function returns a
    Python mapping whose serialized JSON uses the contract's exact field names.
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
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    schema = json.dumps(_bill_schema(), ensure_ascii=False)
    prompt = f"""Read this BSES Rajdhani Power Limited (BRPL) Domestic electricity bill.
Extract only information visibly supported by the bill. Do not guess or use
external tariff knowledge. Return one JSON object only, matching this schema
exactly (no markdown, commentary, or additional keys):
{schema}

For unreadable, absent, or inapplicable data use null, and include the JSON
field path in missing_fields. For arrays, use [] if the bill explicitly has no
entries; use null if the information cannot be read. Keep uncertainties as a
JSON string array. Use numeric JSON values for readable amounts and rates.
Set discom to "BRPL" and category to "Domestic". Set retrieved_at to
"{retrieved_at}". A local bill file does not have a public source URL, so use
null for source_url unless the bill itself prints a source URL. Include other
sources only when an actual URL is printed on the bill."""

    repair_context = ""
    with genai.Client(api_key=api_key) as client:
        for attempt in range(2):
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, repair_context, file_part] if repair_context else [prompt, file_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            response_text = response.text or ""
            try:
                return _parse_and_validate(response_text, retrieved_at)
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
                if attempt == 1:
                    raise ValueError(
                        "Gemini returned invalid bill JSON after one retry."
                    ) from exc
                repair_context = (
                    "Your previous response was invalid JSON or failed schema validation. "
                    "Return a corrected JSON object matching the schema exactly. "
                    "Validation error: "
                    + str(exc)
                    + "\nPrevious response:\n"
                    + response_text
                )
    raise RuntimeError("Gemini did not return a bill response.")


__all__ = ["extract_bill"]
