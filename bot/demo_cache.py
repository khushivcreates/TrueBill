"""Demo: same file twice -> second run uses the extraction cache."""

import logging
from pathlib import Path

from processor import process_bill
from test_pipeline import make_sample_pdf

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")


def main() -> None:
    path = make_sample_pdf(Path(__file__).parent / "cache_demo.pdf")
    try:
        for run in (1, 2):
            result = process_bill(path)
            error = result.get("error")
            if error:
                print(f"run {run}: ERROR: {error[:70]}")
            else:
                print(f"run {run}: checks={len(result.get('checks', []))}")
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
