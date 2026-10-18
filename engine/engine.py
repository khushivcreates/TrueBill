from decimal import Decimal

TOLERANCE = Decimal("1")  # allow 1 rupee difference


def D(value):
    """Turn a number into a Decimal (exact money maths)."""
    return Decimal(str(value))


def expected_energy(units, slabs):
    """Apply each slab's rate only to the units inside that slab."""
    total = Decimal("0")
    for slab in slabs:
        start = D(slab["from_units"])
        end = D(slab["to_units"]) if slab.get("to_units") is not None else units
        units_in_slab = min(units, end) - start
        if units_in_slab > 0:
            total += units_in_slab * D(slab["rate_per_unit"])
    return total


def make_check(item, billed, expected, note_ok, note_warn):
    """Compare billed vs expected and build one check item."""
    ok = abs(billed - expected) <= TOLERANCE
    return {
        "item": item,
        "status": "ok" if ok else "warning",
        "billed": float(billed),
        "expected": float(expected),
        "note": note_ok if ok else note_warn,
    }


def audit(bill, tariff):
    checks = []
    uncertainties = []

    # 1. Wrong tariff for this bill? Stop and say so.
    if bill.get("discom") != tariff.get("discom") or bill.get("category") != tariff.get("category"):
        return {
            "checks": [],
            "uncertainties": [
                "Bill discom/category does not match the tariff, so no audit was done."
            ],
        }

    missing = bill.get("missing_fields") or []
    charges = bill.get("charges") or {}

    def get(name, value):
        """Return value, or None if it is missing (never guess)."""
        if name in missing or value is None:
            return None
        return value

    units = get("units_consumed", bill.get("units_consumed"))
    load_kw = get("sanctioned_load_kw", bill.get("sanctioned_load_kw"))
    billed_energy = get("energy", charges.get("energy"))
    billed_fixed = get("fixed", charges.get("fixed"))
    billed_surcharges = get("surcharges", charges.get("surcharges"))

    # 2. Energy charge
    exp_energy = None
    if units is None:
        uncertainties.append("Units consumed is missing, so energy and surcharge checks were skipped.")
    else:
        exp_energy = expected_energy(D(units), tariff["energy_slabs"])
        if billed_energy is None:
            uncertainties.append("Billed energy charge is missing, so that check was skipped.")
        else:
            checks.append(make_check(
                "Energy charge", D(billed_energy), exp_energy,
                "Matches the tariff slabs.",
                "Does not match the tariff slabs.",
            ))

    # 3. Fixed charge (assumes a 1-month billing period)
    if load_kw is None:
        uncertainties.append("Sanctioned load (kW) is missing, so the fixed charge check was skipped.")
    elif billed_fixed is None:
        uncertainties.append("Billed fixed charge is missing, so that check was skipped.")
    else:
        exp_fixed = D(load_kw) * D(tariff["fixed_charge"]["rate"])
        checks.append(make_check(
            "Fixed charge", D(billed_fixed), exp_fixed,
            "Matches the tariff.",
            "Does not match the tariff.",
        ))

    # 4. Surcharges
    if exp_energy is not None:
        if billed_surcharges is None:
            uncertainties.append("Billed surcharges are missing, so that check was skipped.")
        else:
            exp_surcharges = Decimal("0")
            for s in tariff.get("surcharges", []):
                if s["type"] == "percent_of_energy":
                    exp_surcharges += exp_energy * D(s["value"]) / Decimal("100")
                else:
                    uncertainties.append(f"Unknown surcharge type: {s['type']}")
            checks.append(make_check(
                "Surcharges", D(billed_surcharges), exp_surcharges,
                "Matches the tariff.",
                "Does not match the tariff.",
            ))

    return {"checks": checks, "uncertainties": uncertainties}