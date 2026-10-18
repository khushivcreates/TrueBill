"""Tests for the Gemini retry/logging behaviour in bill_extractor._call_gemini.

Mocks the genai client and time.sleep so no real API calls or waits happen.
Run: python test_retry.py
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

from google.genai import errors

import bill_extractor
from bill_extractor import MODEL, ExtractionError, _call_gemini


def api_error(status: int) -> errors.APIError:
    return errors.APIError(status, {"error": {"message": "mock failure"}})


class CaptureLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def run_case(name, side_effects, expect_status=None, expect_raises=True,
             expect_waits=(), expect_attempts=None):
    """Run _call_gemini with mocked client; return (error_message, log_lines, waits)."""
    capture = CaptureLog()
    extractor_log = logging.getLogger("truebill.extractor")
    extractor_log.addHandler(capture)
    extractor_log.setLevel(logging.INFO)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"discom": "BRPL"}'
    mock_client.models.generate_content.side_effect = side_effects

    waits = []
    with patch.object(bill_extractor.genai, "Client", return_value=mock_client), \
         patch.object(bill_extractor.time, "sleep", side_effect=waits.append), \
         patch.dict(os.environ, {"GEMINI_API_KEY": "fake-test-key-not-real"}):
        try:
            result = _call_gemini(b"%PDF-fake", "application/pdf")
            error_msg, got_result = None, result
        except ExtractionError as exc:
            error_msg, got_result = str(exc), None

    extractor_log.removeHandler(capture)
    return name, error_msg, got_result, capture.lines, waits


def main():
    failures = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    # Case 1: 429, 429, then success -> waits 5, 15 and returns parsed JSON
    name, err, res, logs, waits = run_case(
        "429-then-success",
        [api_error(429), api_error(429), MagicMock(text='{"ok": true}')],
    )
    check("retries 429 and eventually succeeds", res == {"ok": True}, f"err={err}")
    check("waits 5s then 15s on 429", waits == [5, 15], f"waits={waits}")
    check("logs APIError type and HTTP 429",
          any("APIError" in l and "429" in l for l in logs), f"logs={logs}")
    check("log never contains the API key",
          all("fake-test-key-not-real" not in l for l in logs))

    # Case 2: four 429s -> waits 5, 15, 30, then unavailable message
    name, err, res, logs, waits = run_case(
        "429-exhausted",
        [api_error(429)] * 4,
    )
    check("waits 5, 15, 30 on repeated 429", waits == [5, 15, 30], f"waits={waits}")
    check("shows unavailable message after exhausting retries",
          err is not None and "vision service is unavailable" in err, f"err={err}")

    # Case 3: 503 behaves like 429
    name, err, res, logs, waits = run_case(
        "503-then-success",
        [api_error(503), MagicMock(text='{"ok": true}')],
    )
    check("retries 503 with 5s wait", res == {"ok": True} and waits == [5],
          f"err={err}, waits={waits}")

    # Case 4: 404 -> invalid model name message, no retries
    name, err, res, logs, waits = run_case("404", [api_error(404)])
    check("404 says the model name is invalid",
          err is not None and f"'{MODEL}'" in err and "invalid" in err, f"err={err}")
    check("404 does not retry", waits == [], f"waits={waits}")
    check("404 logged with HTTP 404",
          any("404" in l for l in logs), f"logs={logs}")

    # Case 5: non-retryable 400 -> no retry, unavailable message
    name, err, res, logs, waits = run_case("400", [api_error(400)])
    check("400 does not retry", waits == [], f"waits={waits}")
    check("400 shows unavailable message",
          err is not None and "vision service is unavailable" in err, f"err={err}")
    check("400 logged with HTTP 400",
          any("400" in l for l in logs), f"logs={logs}")

    # Case 6: network error (no HTTP status) -> no retry, unavailable message
    import httpx
    name, err, res, logs, waits = run_case(
        "network-error", [httpx.ConnectError("boom")]
    )
    check("network error does not retry", waits == [], f"waits={waits}")
    check("network error logged with type and HTTP None",
          any("ConnectError" in l and "None" in l for l in logs), f"logs={logs}")
    check("network error shows unavailable message",
          err is not None and "vision service is unavailable" in err, f"err={err}")
    check("network error log never contains exception text/headers",
          all("boom" not in l for l in logs), f"logs={logs}")

    # Case 7: exhausted 503s -> unavailable message after all waits
    name, err, res, logs, waits = run_case("503-exhausted", [api_error(503)] * 4)
    check("503 exhausted waits 5, 15, 30", waits == [5, 15, 30], f"waits={waits}")
    check("503 exhausted shows unavailable message",
          err is not None and "vision service is unavailable" in err, f"err={err}")

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        raise SystemExit(1)
    print("All retry/logging tests passed.")


if __name__ == "__main__":
    main()
