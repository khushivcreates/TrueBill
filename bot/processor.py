"""Bill processing stub.

Real flow later: extract Bill JSON from the file, ask the engine's
POST /audit (port 8000) for the Audit JSON. For now process_bill returns a
sample audit matching CONTRACT.md section 3.
"""

from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}


def is_supported(file_path: str | Path) -> bool:
    """True when the file looks like a photo or a PDF."""
    return Path(file_path).suffix.lower() in ALLOWED_EXTENSIONS


def process_bill(file_path: str | Path) -> dict:
    """Process a downloaded bill file and return an Audit JSON dict.

    Stub: ignores the file contents and returns a realistic sample audit.
    Replace the body with real extraction + engine /audit call.
    """
    _ = Path(file_path)  # real implementation reads the file here

    return {
        "checks": [
            {
                "item": "Energy charge",
                "status": "ok",
                "billed": 1146.4,
                "expected": 1146.4,
                "note": "Slab-wise energy charge matches the BRPL domestic tariff.",
            },
            {
                "item": "Fixed charge",
                "status": "warning",
                "billed": 110.0,
                "expected": 95.0,
                "note": "Billed on 2 kW; consumption history suggests 1.5 kW apply.",
            },
            {
                "item": "Electric duty surcharge",
                "status": "ok",
                "billed": 57.32,
                "expected": 57.32,
                "note": "5% of energy + fixed, as per tariff.",
            },
            {
                "item": "FMRA cess",
                "status": "ok",
                "billed": 17.2,
                "expected": 17.2,
                "note": "1.5% of energy charge, as per tariff.",
            },
        ],
        "explanation": (
            "Your bill is mostly correct. The energy charge, electric duty and "
            "FMRA cess all match the published BRPL domestic tariff.\n\n"
            "The only discrepancy is the fixed charge: you were billed Rs. 110.00 "
            "for a 2 kW load, but the tariff rate for your slab is Rs. 95.00. "
            "This overcharge of Rs. 15.00 is small, but you can ask BSES to "
            "correct the sanctioned load on your connection."
        ),
        "sources": [
            {
                "title": "BRPL Domestic Tariff (2024-25)",
                "url": "https://www.bsesdelhi.com/content/domestic-tariff",
                "effective_date": "2024-04-01",
            },
            {
                "title": "Delhi Electricity Regulatory Commission tariff order",
                "url": "https://www.derc.gov.in/orders-notifications/",
                "effective_date": "2024-04-01",
            },
        ],
        "uncertainties": [
            "Sanctioned load could not be verified from the bill photo; "
            "the 2 kW vs 1.5 kW difference needs confirmation.",
            "FPPA for the billing month was applied as per the latest public "
            "notice; DERC may revise it retrospectively.",
        ],
        "draft_complaint": (
            "To: BSES Rajdhani Power Limited\n"
            "Subject: Discrepancy in fixed charge on my electricity bill\n\n"
            "I am a domestic consumer. My recent bill charges a fixed charge of "
            "Rs. 110.00 based on 2 kW, whereas the applicable slab rate works out "
            "to Rs. 95.00. Kindly verify my sanctioned load and revise the fixed "
            "charge accordingly, with a correction in the next billing cycle."
        ),
    }
