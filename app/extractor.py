import anthropic
import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

EXTRACTION_PROMPT = """You are a receipt and invoice data extractor. Extract all information from this document and return ONLY valid JSON — no explanation, no markdown, just the raw JSON object.

Use this exact structure:
{
  "company_name": "string",
  "document_type": "receipt | invoice | utility_bill | other",
  "date": "YYYY-MM-DD or null",
  "currency": "EUR | GBP | USD | etc",
  "total_amount": number or null,
  "line_items": [
    {
      "description": "string",
      "quantity": number,
      "unit_price": number,
      "total_price": number,
      "category": "string or null"
    }
  ]
}

Rules:
- Dates must be in YYYY-MM-DD format
- Prices must be decimal numbers, never strings
- If a value cannot be determined, use null
- Include ALL line items visible — do not skip any
- For utility bills, treat each charge line as a line item
- For utility bill line items, use only the stable charge name as the description (e.g. "Contracted Power P1", "Energy P1", "Meter Hire", "VAT (21%)") — do not append quantities, rates or calculated values to the description; those values belong in the qty and unit_price fields
- For Spanish supermarket receipts (e.g. Aldi, Mercadona, Consum), items are listed as "ITEM NAME   PRICE € VAT_CODE" where the trailing single digit (2, 3, 4 etc.) is a VAT rate code — ignore it, do NOT treat it as a quantity or price
- When a line shows "N x PRICE €" immediately before or above an item, N is the quantity and PRICE is the unit price for that item; otherwise quantity defaults to 1
- Discounts appear as negative prices — include them as line items with negative unit_price and total_price
- unit_price and total_price must always be a number — use 0 for zero-value items, never null for these fields
- When quantity is 1 and no unit price is shown on the receipt, set unit_price equal to total_price
- For weighed items on supermarket receipts, the line below the item name shows "X,XXX kg  Y,YY €/kg  TOTAL" — extract quantity=X.XXX (in kg), unit_price=Y.YY (price per kg), total_price=TOTAL
- For category, pick the most appropriate from:
- If the description contains "VAT", "IVA", or "impuesto", always assign category "tax"
  food, drink, dairy, meat, fish, bakery, produce, frozen,
  household, cleaning, personal_care, pet,
  electricity, water, gas, internet, phone,
  restaurant, takeaway, tax, other
"""


def extract_from_file(filepath: str, template_items: list = None) -> dict:
    """
    Extract structured data from a receipt or invoice image or PDF.

    Returns a dict with keys: company_name, document_type, date, currency,
    total_amount, line_items — or raises ExtractionError on failure.
    """
    suffix = os.path.splitext(filepath)[1].lower()

    if suffix == ".pdf":
        content = _build_pdf_content(filepath, template_items)
    elif suffix in (".jpg", ".jpeg", ".png"):
        content = _build_image_content(filepath, template_items)
    else:
        raise ExtractionError(f"Unsupported file type: {suffix}")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    system = [{"type": "text", "text": EXTRACTION_PROMPT, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIConnectionError as e:
        raise ExtractionError(f"Could not connect to Anthropic API: {e}")
    except anthropic.AuthenticationError:
        raise ExtractionError("Invalid Anthropic API key. Check your .env file.")
    except anthropic.RateLimitError:
        raise ExtractionError("Anthropic API rate limit reached. Please wait and try again.")
    except anthropic.APIError as e:
        raise ExtractionError(f"Anthropic API error: {e}")

    raw_text = response.content[0].text
    return _parse_response(raw_text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_image_content(filepath: str, template_items: list) -> list:
    suffix = os.path.splitext(filepath)[1].lower()
    media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    with open(filepath, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
            },
        },
    ]
    hint = _build_hint(template_items)
    if hint:
        content.append({"type": "text", "text": hint})
    return content


def _build_pdf_content(filepath: str, template_items: list) -> list:
    with open(filepath, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_data,
            },
        },
    ]
    hint = _build_hint(template_items)
    if hint:
        content.append({"type": "text", "text": hint})
    return content


def _build_hint(template_items: list) -> str | None:
    if template_items:
        hint = json.dumps(template_items, indent=2)
        return f"Known items from this company (use for category hints):\n{hint}"
    return None


def _parse_response(raw_text: str) -> dict:
    """Parse JSON from Claude's response, stripping markdown fences if present."""
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Could not parse Claude response as JSON: {e}\n\nRaw response:\n{raw_text}")

    _validate(data)
    return data


def _validate(data: dict):
    """Basic validation that required keys are present."""
    required = {"company_name", "document_type", "line_items"}
    missing = required - data.keys()
    if missing:
        raise ExtractionError(f"Extraction response missing required fields: {missing}")
    if not isinstance(data["line_items"], list):
        raise ExtractionError("line_items must be a list")


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """Raised when receipt extraction fails."""
    pass
