"""Run the BRPL bill extractor for every file under sample_bills/."""

from __future__ import annotations

import json
from pathlib import Path

from bill_extractor import extract_bill


BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "sample_bills"


def main() -> None:
    files = sorted(path for path in SAMPLES_DIR.rglob("*") if path.is_file()) if SAMPLES_DIR.exists() else []
    results = []
    for path in files:
        try:
            results.append(
                {
                    "file": str(path.relative_to(BASE_DIR)),
                    "result": extract_bill(path),
                }
            )
        except Exception as exc:
            # Avoid printing exception text that could contain request details.
            results.append(
                {
                    "file": str(path.relative_to(BASE_DIR)),
                    "error": type(exc).__name__,
                }
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
