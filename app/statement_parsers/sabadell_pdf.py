"""Parser for Banco Sabadell PDF movement query exports."""
import re
import io
from pypdf import PdfReader

OWN_NAME_UPPER = 'NIGEL RICHARD HORNCASTLE'

_CONCEPT_PREFIXES = [
    'PURCHASE RETURN BIZUM ',
    'PURCHASE RETURN ',
    'PURCHASE BIZUM ',
    'DIRECT DEBIT ',
    'TRANSFER TO ',
    'PURCHASE ',
]

_ROW_RE = re.compile(
    r'^' + r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})\s*$',
    re.MULTILINE,
)


def _clean_description(concept: str) -> str:
    c = concept.strip()
    c_upper = c.upper()
    for prefix in _CONCEPT_PREFIXES:
        if c_upper.startswith(prefix):
            desc = c[len(prefix):].strip()
            # For BIZUM: keep only the first word (merchant name).
            if 'BIZUM' in prefix:
                desc = desc.split()[0] if desc.split() else desc
            return desc.title()
    return c.title()


def _parse_amount(s: str) -> float:
    """Spanish format: -1.154,08 → -1154.08"""
    return float(s.strip().replace('.', '').replace(',', '.'))


def _should_skip(concept: str) -> bool:
    c = concept.upper()
    if OWN_NAME_UPPER in c:
        return True
    if c.startswith('CREDIT CARD'):
        return True
    return False


def parse(file_bytes: bytes) -> list:
    """Parse Sabadell PDF bytes into a list of transaction dicts."""
    reader = PdfReader(io.BytesIO(file_bytes))
    text = '\n'.join(p.extract_text() or '' for p in reader.pages)

    rows = []
    seen_ids = set()

    for m in _ROW_RE.finditer(text):
        oper_date_str = m.group(1)
        concept = m.group(2).strip()
        amount_str = m.group(4)

        if _should_skip(concept):
            continue

        try:
            amount = _parse_amount(amount_str)
        except ValueError:
            continue
        if amount == 0:
            continue

        direction = 'in' if amount > 0 else 'out'
        amount = abs(amount)

        d, mo, y = oper_date_str.split('/')
        date_str = f'{y}-{mo}-{d}'

        description = _clean_description(concept)

        # Synthetic dedup ID
        raw_amt = amount_str.replace('.', '').replace(',', '').replace('-', '')
        tx_id = f'sabadell_{date_str}_{raw_amt}'
        suffix = 0
        base_id = tx_id
        while tx_id in seen_ids:
            suffix += 1
            tx_id = f'{base_id}_{suffix}'
        seen_ids.add(tx_id)

        rows.append({
            'date':           date_str,
            'description':    description,
            'amount':         amount,
            'direction':      direction,
            'category':       'other',
            'transaction_id': tx_id,
            'source':         'sabadell_pdf',
            'notes':          None,
        })

    return rows
