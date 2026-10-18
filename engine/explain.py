import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-3.8-flash"


def build_prompt(audit_result, bill, tariff):
    facts = {
        "checks": audit_result.get("checks", []),
        "uncertainties": audit_result.get("uncertainties", []),
        "units_consumed": bill.get("units_consumed"),
        "billing_period": bill.get("billing_period"),
        "consumer_name": bill.get("consumer_name"),
        "discom": bill.get("discom"),
        "tariff_source_url": tariff.get("source_url"),
        "tariff_effective_date": tariff.get("effective_date"),
    }
    has_warning = any(c["status"] == "warning" for c in facts["checks"])

    return f"""You are explaining an electricity bill audit to an ordinary household customer.

STRICT RULES:
- Do NOT calculate or change any number. Use ONLY the numbers in the FACTS below.
- Never invent numbers, reasons, or rules that are not in the FACTS.
- Write the explanation in plain, simple language, 4 to 6 sentences.
- Mention possible reasons for a high bill (consumption, billing period length, surcharges) ONLY if the FACTS support it.
- Mention the tariff source URL and effective date.
- State the uncertainties honestly. If there are none, do not make any up.
- If a check is "warning", write a polite draft clarification request to the discom, including the consumer name, billing period, and the exact billed and expected figures.
- If every check is "ok", draft_complaint must be an empty string.

Has warning: {has_warning}

FACTS:
{json.dumps(facts, indent=2)}

Reply with ONLY a JSON object with two string fields: "explanation" and "draft_complaint"."""


def explain(audit_result, bill, tariff):
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=MODEL,
            contents=build_prompt(audit_result, bill, tariff),
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        return {
            "explanation": str(data.get("explanation", "")),
            "draft_complaint": str(data.get("draft_complaint", "")),
        }
    except Exception as e:
        # If Gemini fails, still return the audit instead of crashing
        print("Gemini error:", e)
        return {
            "explanation": "An automatic explanation is not available right now. Please read the check results above.",
            "draft_complaint": "",
        }