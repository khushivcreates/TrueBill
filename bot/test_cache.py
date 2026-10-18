"""Tests for the extraction cache in bill_extractor.extract_bill.

Mocks _call_gemini so no real API calls happen. Verifies: cache hit skips
Gemini, failures are never cached, corrupt entries are re-extracted.
Run: python test_cache.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import bill_extractor
from bill_extractor import ExtractionError, extract_bill

TEST_DIR = Path(__file__).resolve().parent / "test_cache_tmp"

GOOD_REPLY = {
    "discom": "BRPL",
    "category": "Domestic",
    "consumer_name": "Test User",
    "billing_period": {"start": "2026-09-01", "end": "2026-09-30"},
    "units_consumed": 320,
    "sanctioned_load_kw": 5.0,
    "charges": {"energy": 1320.0, "fixed": 250.0, "surcharges": 184.5,
                "other": None, "total": 1754.5},
    "missing_fields": [],
}

# Bill missing required fields -> must NOT be cached.
PARTIAL_REPLY = {
    "discom": "BRPL",
    "category": "Domestic",
    "units_consumed": None,
    "sanctioned_load_kw": None,
    "charges": {"energy": None, "fixed": None, "surcharges": None},
    "missing_fields": ["units_consumed", "sanctioned_load_kw", "energy",
                       "fixed", "surcharges"],
}


class CaptureLog(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def cache_entries() -> list[Path]:
    cache_dir = bill_extractor.EXTRACT_CACHE_DIR
    return sorted(cache_dir.glob("*.json")) if cache_dir.exists() else []


def main():
    failures = []

    def check(name, cond, detail=""):
        print(f"[{'PASS' if cond else 'FAIL'}] {name}"
              + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    TEST_DIR.mkdir(exist_ok=True)
    bill_file = TEST_DIR / "bill.pdf"
    bill_file.write_bytes(b"%PDF-1.4 fake bill bytes for cache test")
    expected_name = hashlib.sha256(bill_file.read_bytes()).hexdigest() + ".json"

    # Start from a clean cache dir for this file's hash.
    (bill_extractor.EXTRACT_CACHE_DIR / expected_name).unlink(missing_ok=True)

    capture = CaptureLog()
    ext_log = logging.getLogger("truebill.extractor")
    ext_log.addHandler(capture)
    ext_log.setLevel(logging.INFO)

    gemini = MagicMock(return_value=GOOD_REPLY)

    # 1. First call: Gemini called once, cache file created with sha256 name.
    with patch.object(bill_extractor, "_call_gemini", gemini):
        bill1 = extract_bill(bill_file)
    check("first call goes to Gemini", gemini.call_count == 1)
    check("first call does not log cache hit",
          not any("using cached extraction" in l for l in capture.lines))
    entry = bill_extractor.EXTRACT_CACHE_DIR / expected_name
    check("cache file named <sha256>.json exists", entry.is_file(),
          f"expected {expected_name}, have {[p.name for p in cache_entries()]}")
    cached_json = json.loads(entry.read_text(encoding="utf-8"))
    check("cached JSON equals returned bill", cached_json == bill1)
    check("cached bill keeps sanctioned_load_kw",
          cached_json.get("sanctioned_load_kw") == 5.0)

    # 2. Second call: same file -> cached, Gemini NOT called, log line shown.
    capture.lines.clear()
    with patch.object(bill_extractor, "_call_gemini", gemini):
        bill2 = extract_bill(bill_file)
    check("second call does NOT call Gemini", gemini.call_count == 1)
    check("second call returns identical bill", bill2 == bill1)
    check("logs 'using cached extraction'",
          any("using cached extraction" in l for l in capture.lines),
          f"logs={capture.lines}")

    # 3. Failed extraction (unreadable fields) -> never cached.
    partial_file = TEST_DIR / "partial.pdf"
    partial_file.write_bytes(b"%PDF-1.4 another bill")
    partial_digest = hashlib.sha256(partial_file.read_bytes()).hexdigest()
    with patch.object(bill_extractor, "_call_gemini", return_value=PARTIAL_REPLY):
        try:
            extract_bill(partial_file)
            raised = False
        except ExtractionError:
            raised = True
    check("failed extraction raises friendly error", raised)
    check("failed extraction is not cached",
          not (bill_extractor.EXTRACT_CACHE_DIR / f"{partial_digest}.json").exists())

    # 4. Failed extraction (not a bill -> {}) -> never cached.
    nobill_file = TEST_DIR / "nobill.pdf"
    nobill_file.write_bytes(b"%PDF-1.4 not a bill at all")
    nobill_digest = hashlib.sha256(nobill_file.read_bytes()).hexdigest()
    with patch.object(bill_extractor, "_call_gemini", return_value={}):
        try:
            extract_bill(nobill_file)
            raised = False
        except ExtractionError:
            raised = True
    check("non-bill file raises friendly error", raised)
    check("non-bill result is not cached",
          not (bill_extractor.EXTRACT_CACHE_DIR / f"{nobill_digest}.json").exists())

    # 5. Gemini raising (service down) -> never cached.
    down_file = TEST_DIR / "down.pdf"
    down_file.write_bytes(b"%PDF-1.4 bill while service down")
    down_digest = hashlib.sha256(down_file.read_bytes()).hexdigest()
    with patch.object(bill_extractor, "_call_gemini",
                      side_effect=ExtractionError("vision service is unavailable")):
        try:
            extract_bill(down_file)
            raised = False
        except ExtractionError:
            raised = True
    check("service-down error propagates", raised)
    check("service-down result is not cached",
          not (bill_extractor.EXTRACT_CACHE_DIR / f"{down_digest}.json").exists())

    # 6. Corrupt cache entry -> treated as miss, re-extracted, re-cached.
    capture.lines.clear()
    entry.write_text("{not valid json", encoding="utf-8")
    gemini_after = MagicMock(return_value=GOOD_REPLY)
    with patch.object(bill_extractor, "_call_gemini", gemini_after):
        bill3 = extract_bill(bill_file)
    check("corrupt cache re-extracts via Gemini", gemini_after.call_count == 1)
    check("corrupt cache entry re-written as valid JSON",
          json.loads(entry.read_text(encoding="utf-8")) == bill3)

    # 7. A different file (different bytes) misses the cache.
    other_file = TEST_DIR / "other.pdf"
    other_file.write_bytes(b"%PDF-1.4 a genuinely different bill")
    gemini_other = MagicMock(return_value=GOOD_REPLY)
    with patch.object(bill_extractor, "_call_gemini", gemini_other):
        extract_bill(other_file)
    check("different file does not hit cache", gemini_other.call_count == 1)

    ext_log.removeHandler(capture)
    shutil.rmtree(TEST_DIR, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        raise SystemExit(1)
    print("All cache tests passed.")


if __name__ == "__main__":
    main()
