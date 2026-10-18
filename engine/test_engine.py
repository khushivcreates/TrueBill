import json
from pathlib import Path

from engine import audit

SAMPLES = Path(__file__).parent / "samples"


def load(name):
    with open(SAMPLES / name) as f:
        return json.load(f)


def get_check(result, item):
    for c in result["checks"]:
        if c["item"] == item:
            return c
    return None


def test_correct_bill_is_all_ok():
    result = audit(load("bill_ok.json"), load("tariff_sample.json"))
    assert len(result["checks"]) == 3
    assert all(c["status"] == "ok" for c in result["checks"])
    assert result["uncertainties"] == []


def test_expected_amounts_match_hand_calculation():
    result = audit(load("bill_ok.json"), load("tariff_sample.json"))
    assert get_check(result, "Energy charge")["expected"] == 825
    assert get_check(result, "Fixed charge")["expected"] == 40
    assert get_check(result, "Surcharges")["expected"] == 82.5


def test_wrong_surcharge_gives_warning():
    result = audit(load("bill_wrong_surcharge.json"), load("tariff_sample.json"))
    assert get_check(result, "Surcharges")["status"] == "warning"
    assert get_check(result, "Energy charge")["status"] == "ok"
    assert get_check(result, "Fixed charge")["status"] == "ok"


def test_missing_units_is_not_guessed():
    bill = load("bill_ok.json")
    bill["units_consumed"] = None
    bill["missing_fields"] = ["units_consumed"]
    result = audit(bill, load("tariff_sample.json"))
    assert get_check(result, "Energy charge") is None
    assert get_check(result, "Surcharges") is None
    assert len(result["uncertainties"]) >= 1


def test_wrong_discom_returns_only_uncertainty():
    bill = load("bill_ok.json")
    bill["discom"] = "TPDDL"
    result = audit(bill, load("tariff_sample.json"))
    assert result["checks"] == []
    assert len(result["uncertainties"]) == 1


def test_long_billing_period_is_not_audited():
    bill = load("bill_ok.json")
    bill["billing_period"] = {"start": "2026-08-01", "end": "2026-09-01"}  # 32 days
    result = audit(bill, load("tariff_sample.json"))
    assert result["checks"] == []
    assert "32 days" in result["uncertainties"][0]