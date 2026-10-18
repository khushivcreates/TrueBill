from datetime import date
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


def expected_fixed(load_kw, fixed_charge):
    """Whole sanctioned load x the rate of the kW band it falls in."""
    if isinstance(fixed_charge, dict):  # old single-rate shape
        return load_kw * D(fixed_charge["rate"])
    for band in fixed_charge:
        low = D(band["from_kw"])
        high = D(band["to_kw"]) if band.get("to_kw") is not None else None
        if load_kw > low and (high is None or load_kw <= high):
            return load_kw * D(band["rate_per_kw_per_month"])
    return None


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

    # Bills longer or shorter than a normal month are prorated by the discom.
    # We don't know the exact rule, so we refuse to guess.
    period = bill.get("billing_period")
    if period and period.get("start") and period.get("end"):
        days = (date.fromisoformat(period["end"]) - date.fromisoformat(period["start"])).days + 1
        if days < 28 or days > 31:
            return {
                "checks": [],
                "uncertainties": [
                    f"The billing period is {days} days. Discoms prorate slabs and fixed charges for such periods and the exact rule is not yet built in, so no charges were checked."
                ] + tariff.get("uncertainties", []),
            }

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
    exp_fixed = None
    if load_kw is None:
        uncertainties.append("Sanctioned load (kW) is missing, so the fixed charge check was skipped.")
    elif billed_fixed is None:
        uncertainties.append("Billed fixed charge is missing, so that check was skipped.")
    else:
        exp_fixed = expected_fixed(D(load_kw), tariff["fixed_charge"])
        if exp_fixed is None:
            uncertainties.append("No fixed-charge band matches the sanctioned load, so that check was skipped.")
        else:
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
            can_compute = True
            for s in tariff.get("surcharges", []):
                if s["type"] == "percent_of_energy":
                    exp_surcharges += exp_energy * D(s["value"]) / Decimal("100")
                elif s["type"] == "percent_of_energy_plus_fixed" and exp_fixed is not None:
                    exp_surcharges += (exp_energy + exp_fixed) * D(s["value"]) / Decimal("100")
                else:
                    can_compute = False
                    uncertainties.append(f"Could not compute surcharge '{s['name']}', so the surcharge check was skipped.")
            if can_compute:
                checks.append(make_check(
                    "Surcharges", D(billed_surcharges), exp_surcharges,
                    "Matches the tariff.",
                    "Does not match the tariff.",
                ))

    # Pass through what the tariff retrieval could not confirm
    uncertainties += tariff.get("uncertainties", [])

    return {"checks": checks, "uncertainties": uncertainties}