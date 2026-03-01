"""
Energy Nordic electricity bill analyser.

Extracts detailed consumption and cost data from page 2 of the PDF only.
Page 2 contains the full billing breakdown as plain text — no images needed,
so this is fast and uses minimal tokens.
Page 3 (contract/useful info) is ignored entirely.
"""

import json
import anthropic
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

PROMPT = """You are extracting structured data from page 2 of a Spanish electricity bill issued by Energy Nordic.

The page contains meter readings, consumption figures, a cost breakdown, and summary stats.

Return ONLY valid JSON — no explanation, no markdown — using this exact structure:

{
  "billing_period": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD",
    "days": number
  },
  "meter_readings": {
    "P1": {"previous": number, "current": number},
    "P2": {"previous": number, "current": number},
    "P3": {"previous": number, "current": number}
  },
  "reading_type": "Real | Estimated | Mixed",
  "contracted_power": {
    "P1": {"kw": number, "rate_per_kw_per_day": number, "days": number, "total": number},
    "P2": {"kw": number, "rate_per_kw_per_day": number, "days": number, "total": number}
  },
  "energy": {
    "P1": {"kwh": number, "energy_price": number, "toll": number, "total": number},
    "P2": {"kwh": number, "energy_price": number, "toll": number, "total": number},
    "P3": {"kwh": number, "energy_price": number, "toll": number, "total": number}
  },
  "handle_fee": number,
  "electricity_tax": {
    "base": number,
    "rate_pct": number,
    "amount": number
  },
  "meter_hire": {
    "days": number,
    "daily_rate": number,
    "total": number
  },
  "tax_base": number,
  "vat": {
    "rate_pct": number,
    "amount": number
  },
  "total": number,
  "avg_daily_cost": number,
  "avg_daily_consumption_kwh": number
}

Rules:
- All monetary values in EUR as decimal numbers
- Use null for any value not present in the text
- Dates in YYYY-MM-DD format
- Comma is used as decimal separator in the source — convert to decimal point
"""


def analyse(filepath: str) -> dict:
    """
    Extract detailed billing data from page 2 of an Energy Nordic PDF.
    Returns a structured dict or raises AnalysisError.
    """
    page2_text = _extract_page_text(filepath, page_index=1)  # page 2 = index 1
    if not page2_text or len(page2_text) < 100:
        raise AnalysisError(f"Could not extract usable text from page 2 of {filepath}")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast + cheap — plain text, no vision needed
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"{PROMPT}\n\n--- PAGE 2 TEXT ---\n{page2_text}"
            }],
        )
    except anthropic.APIConnectionError as e:
        raise AnalysisError(f"API connection error: {e}")
    except anthropic.AuthenticationError:
        raise AnalysisError("Invalid Anthropic API key.")
    except anthropic.APIError as e:
        raise AnalysisError(f"Anthropic API error: {e}")

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AnalysisError(f"Could not parse response as JSON: {e}\n\nRaw:\n{raw}")

    return data


def _extract_page_text(filepath: str, page_index: int) -> str:
    """Extract plain text from a single PDF page (0-indexed)."""
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    if page_index >= len(reader.pages):
        return ""
    return reader.pages[page_index].extract_text() or ""


class AnalysisError(Exception):
    pass
