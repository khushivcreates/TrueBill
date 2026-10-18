from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import audit
from explain import explain

app = FastAPI(title="TrueBill Engine")

# CORS lets other programs (like Khushi's) call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Shapes of the data we accept (from CONTRACT.md) ----
class BillingPeriod(BaseModel):
    start: str
    end: str


class Charges(BaseModel):
    energy: Optional[float] = None
    fixed: Optional[float] = None
    surcharges: Optional[float] = None
    other: Optional[float] = None
    total: Optional[float] = None


class Bill(BaseModel):
    discom: str
    category: str
    consumer_name: Optional[str] = None
    billing_period: Optional[BillingPeriod] = None
    units_consumed: Optional[float] = None
    sanctioned_load_kw: Optional[float] = None
    charges: Charges
    missing_fields: List[str] = []


class Slab(BaseModel):
    from_units: float
    to_units: Optional[float] = None
    rate_per_unit: float


class FixedCharge(BaseModel):
    basis: str
    rate: float


class Surcharge(BaseModel):
    name: str
    type: str
    value: float


class Tariff(BaseModel):
    discom: str
    category: str
    effective_date: str
    energy_slabs: List[Slab]
    fixed_charge: FixedCharge
    surcharges: List[Surcharge] = []
    source_url: str = ""
    retrieved_at: str = ""


class AuditRequest(BaseModel):
    bill: Bill
    tariff: Optional[Tariff] = None


# ---- The endpoints ----
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/audit")
def run_audit(request: AuditRequest):
    bill = request.bill.model_dump()

    # No tariff found: report honestly, do not guess
    if request.tariff is None:
        return {
            "checks": [],
            "explanation": "The bill could not be verified because no official tariff was available for it. No charges were checked.",
            "sources": [],
            "uncertainties": [
                "No tariff was provided, so the charges could not be verified."
            ],
            "draft_complaint": "",
        }

    tariff = request.tariff.model_dump()
    result = audit(bill, tariff)
    extra = explain(result, bill, tariff)

    result["explanation"] = extra["explanation"]
    result["draft_complaint"] = extra["draft_complaint"]
    result["sources"] = [
        {
            "title": f"{tariff['discom']} {tariff['category']} tariff",
            "url": tariff["source_url"],
            "effective_date": tariff["effective_date"],
        }
    ]
    return result