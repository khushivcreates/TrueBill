"""Manual test: build a tiny text PDF bill, run the real pipeline end to end.

Usage: python test_pipeline.py <path-to-bill.(pdf|jpg)>   (optional argument)
With no argument it generates a sample bill PDF first.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from processor import TARIFF_CACHE_PATH, process_bill

SAMPLE_TEXT = """BSES RAJDHANI POWER LIMITED (BRPL)
Electricity Bill
Consumer Name: Ravi Sharma
Consumer No: 1234567890

Billing Period: 01/09/2026 to 30/09/2026
Sanctioned Load: 5.0 kW
Units Consumed: 320

Energy Charge       : 1320.00
Fixed Charge        : 250.00
Electric Duty Surcharge : 78.50
Pension Trust Surcharge : 106.00
Total Amount Payable    : 1754.50
"""


def make_sample_pdf(destination: Path) -> Path:
    """Hand-roll a minimal single-page PDF with extractable text."""
    stream = (
        "BT /F1 11 Tf 40 760 Td 14 TL\n"
        + "".join(f"({line}) Tj T*\n" for line in SAMPLE_TEXT.splitlines())
        + "ET"
    ).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF"
    ).encode()

    destination.write_bytes(bytes(out))
    return destination


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if len(sys.argv) > 1:
        bill_path = Path(sys.argv[1])
    else:
        bill_path = make_sample_pdf(Path(__file__).parent / "sample_bill.pdf")
        print(f"Generated sample bill: {bill_path.name}")

    tariff_hash_before = file_hash(TARIFF_CACHE_PATH)
    print(f"Tariff cache sha256 (before): {tariff_hash_before[:16]}...")

    audit = process_bill(bill_path)

    tariff_hash_after = file_hash(TARIFF_CACHE_PATH)
    print(f"Tariff cache sha256 (after):  {tariff_hash_after[:16]}...")
    print(f"Tariff cache unchanged: {tariff_hash_before == tariff_hash_after}")

    if audit.get("error"):
        print(f"\nFRIENDLY ERROR: {audit['error']}")
    else:
        print("\n--- AUDIT JSON ---")
        for check in audit.get("checks", []):
            print(f"  [{check['status'].upper()}] {check['item']}: "
                  f"billed={check['billed']} expected={check['expected']}")
        print(f"  checks: {len(audit.get('checks', []))}, "
              f"uncertainties: {len(audit.get('uncertainties', []))}")
        print(f"  explanation present: {bool(audit.get('explanation'))}")
        print(f"  sources: {[s.get('title') for s in audit.get('sources', [])]}")

    if not len(sys.argv) > 1:
        bill_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
