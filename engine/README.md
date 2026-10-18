\# TrueBill Engine



Rules engine + audit API + plain-language explanation for TrueBill.



\- \*\*Rules engine\*\* (`engine.py`): recalculates energy, fixed and surcharge amounts from the tariff. Pure Python, no LLM, uses `Decimal` for money.

\- \*\*API\*\* (`main.py`): FastAPI server with `POST /audit` and `GET /health`.

\- \*\*Explanation\*\* (`explain.py`): Gemini explains the engine's results and drafts a complaint. It never does the arithmetic.



\## Setup



1\. Install Python 3.9 or higher.

2\. Install the packages:



```bash

pip install -r requirements.txt

```



3\. Create a file named `.env` in this folder with your Gemini key (never commit this file):



```

GEMINI\_API\_KEY=your\_key\_here

```



\## Run the API



```bash

uvicorn main:app --reload --port 8000

```



\- Health check: http://127.0.0.1:8000/health

\- Interactive docs: http://127.0.0.1:8000/docs



\## Run the tests



```bash

pytest

```



\## Sample data



`samples/` has a placeholder tariff and two test bills (one correct, one with a wrong surcharge). The tariff rates are placeholders, not real BRPL rates.



\## Behaviour on missing data



The engine never guesses. If a field is missing, that check is skipped and listed under `uncertainties`. If the bill's discom or category does not match the tariff, or no tariff is provided, no checks run and an uncertainty is returned.




## Known limits

- Bills whose billing period is not 28 to 31 days are not audited. Discoms prorate slabs and fixed charges for those, and the exact rule is not built in yet. The API returns an uncertainty instead.
- FPPA is not checked yet.
- The fixed charge check assumes a one-month period.