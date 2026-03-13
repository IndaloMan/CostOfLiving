"""
Generic Spanish electricity bill analyser.

Extracts detailed consumption and cost data from any Spanish electricity bill PDF.
All pages are extracted as plain text and sent together — no page number assumptions.
"""

import json
import anthropic
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

PROMPT = """You are extracting structured data from a Spanish electricity bill.

The text may come from one or more pages of the bill. Extract all meter readings,
consumption figures, cost breakdown, and summary stats you can find.

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
  "_energy_units_note": "energy_price and toll are RATES in euros/kWh (e.g. 0.1595), NOT total costs in euros. They should be small decimals well below 1.0.",
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
- IMPORTANT: energy_price and toll must be the per-unit RATES in euros/kWh as printed
  on the bill (e.g. 0.1595 and 0.0925), NOT the calculated totals in euros.
  Spanish electricity rates are always between 0.01 and 0.99 euros/kWh.
"""


def analyse(filepath: str) -> dict:
    """
    Extract detailed billing data from a Spanish electricity bill PDF.
    Reads all pages and sends them as plain text. Returns a structured dict
    or raises AnalysisError.
    """
    all_text = _extract_all_pages_text(filepath)
    if not all_text or len(all_text) < 100:
        raise AnalysisError(f"Could not extract usable text from {filepath}")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"{PROMPT}\n\n--- BILL TEXT ---\n{all_text}"
            }],
        )
    except anthropic.APIConnectionError as e:
        raise AnalysisError(f"API connection error: {e}")
    except anthropic.AuthenticationError:
        raise AnalysisError("Invalid Anthropic API key.")
    except anthropic.APIError as e:
        raise AnalysisError(f"Anthropic API error: {e}")

    raw = response.content[0].text.strip()

    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AnalysisError(f"Could not parse response as JSON: {e}\n\nRaw:\n{raw}")

    data.pop("_energy_units_note", None)
    _correct_energy_rates(data)
    return data


def _correct_energy_rates(data: dict):
    """
    Guard against Claude returning total euro costs instead of euros/kWh rates.
    Spanish electricity rates are always in the range 0.01-0.99 euros/kWh.
    """
    energy = data.get("energy", {})
    for period in ("P1", "P2", "P3"):
        p = energy.get(period)
        if not p:
            continue
        kwh = p.get("kwh") or 0
        if kwh <= 0:
            continue
        for field in ("energy_price", "toll"):
            val = p.get(field)
            if val is not None and val > 2.0:
                p[field] = round(val / kwh, 6)


def _extract_all_pages_text(filepath: str) -> str:
    """Extract and concatenate plain text from all pages of a PDF."""
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(f"--- Page {i + 1} ---\n{text}")
    return "\n\n".join(parts)


class AnalysisError(Exception):
    pass
