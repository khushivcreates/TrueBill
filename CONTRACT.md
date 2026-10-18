# TrueBill Contract

Discom: BSES Rajdhani Power Limited (BRPL) | Category: Domestic (household)

Rule: if code and this file disagree, this file is right. Change it only after both of us agree.

## Folders
- `/bot`        Khushi: Telegram bot, bill extraction, /process endpoint
- `/retrieval`  Khushi: TinyFish tariff retrieval
- `/engine`     Lakshay: rules engine, FastAPI /audit, LLM explanation
- repo root     Web front end (Google AI Studio export: src, index.html, vite config)

## 1. Bill JSON (Khushi's extraction produces it)
```json
{
  "discom": "BRPL",
  "category": "Domestic",
  "effective_date": "YYYY-MM-DD",
  "energy_slabs": [{"from_units": 0, "to_units": 200, "rate_per_unit": 0}],
  "fixed_charge": [{"from_kw": 0, "to_kw": 2, "rate_per_kw_per_month": 0}],
  "surcharges": [{"name": "", "type": "percent_of_energy_plus_fixed", "value": 0, "effective_date": ""}],
  "fppas_by_month": [{"month": "YYYY-MM", "percent": 0, "source_url": ""}],
  "source_url": "",
  "other_sources": [{"component": "", "url": ""}],
  "uncertainties": [],
  "retrieved_at": ""
}
```

## 2. Tariff JSON (Khushi's TinyFish retrieval produces it)
```json
{
  "discom": "BRPL",
  "category": "Domestic",
  "effective_date": "YYYY-MM-DD",
  "energy_slabs": [{"from_units": 0, "to_units": 200, "rate_per_unit": 0}],
  "fixed_charge": [{"from_kw": 0, "to_kw": 2, "rate_per_kw_per_month": 0}],
  "surcharges": [{"name": "", "type": "percent_of_energy_plus_fixed", "value": 0, "effective_date": ""}],
  "fppas_by_month": [{"month": "YYYY-MM", "percent": 0, "source_url": ""}],
  "source_url": "",
  "other_sources": [{"component": "", "url": ""}],
  "uncertainties": [],
  "retrieved_at": ""
}
```

Slabs are continuous (0-200, 200-400, ...). Fixed charge = sanctioned load x band rate. The "tariff_cache/brpl_domestic.json" file is the reference


## 3. Audit JSON (Lakshay's API returns it)
```json
{
  "checks": [{"item": "Energy charge", "status": "ok", "billed": 0, "expected": 0, "note": ""}],
  "explanation": "",
  "sources": [{"title": "", "url": "", "effective_date": ""}],
  "uncertainties": [],
  "draft_complaint": ""
}
```
`status` is either `"ok"` or `"warning"`.

## Endpoints
- Lakshay: `POST /audit` takes `{"bill": <Bill JSON>, "tariff": <Tariff JSON>}`, returns Audit JSON (port 8000)
- Khushi: `POST /process` takes an uploaded file (form field `file`), returns Audit JSON
