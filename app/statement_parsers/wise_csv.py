"""Parser for Wise card statement CSV exports."""
import csv
import io

OWN_NAME_UPPER = 'NIGEL RICHARD HORNCASTLE'

WISE_CATEGORY_MAP = {
    'Groceries':   'food',
    'Entertainment': 'other',
    'Bills':       'other',
    'Shopping':    'other',
    'Eating out':  'restaurant',
    'Rewards':     'other',
    'General':     'other',
}


def parse(file_bytes: bytes) -> list:
    """Parse Wise CSV bytes into a list of transaction dicts."""
    text = file_bytes.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    rows = []

    for row in reader:
        status = row.get('Status', '').strip()
        if status != 'COMPLETED':
            continue

        direction = row.get('Direction', '').strip()
        if direction == 'NEUTRAL':
            continue

        tx_id = row.get('ID', '').strip()
        tx_type = tx_id.split('-')[0] if '-' in tx_id else tx_id

        # Skip internal currency conversions
        if tx_type == 'BALANCE_TRANSACTION':
            continue

        target_name = row.get('Target name', '').strip()

        # Skip own-account transfers (Wise → Sabadell top-ups)
        if tx_type == 'TRANSFER' and OWN_NAME_UPPER in target_name.upper():
            continue

        created_on = row.get('Created on', '').strip()
        if not created_on:
            continue
        date_str = created_on[:10]  # "2026-03-06 07:51:41" → "2026-03-06"

        description = target_name or row.get('Source name', '').strip()

        amount_str = row.get('Source amount (after fees)', '0').strip()
        try:
            amount = abs(float(amount_str))
        except ValueError:
            continue
        if amount == 0:
            continue

        wise_cat = row.get('Category', '').strip()
        category = WISE_CATEGORY_MAP.get(wise_cat, 'other')

        reference = row.get('Reference', '').strip()
        note = row.get('Note', '').strip()
        notes = reference or note or None

        rows.append({
            'date':           date_str,
            'description':    description,
            'amount':         amount,
            'direction':      'in' if direction == 'IN' else 'out',
            'category':       category,
            'transaction_id': tx_id,
            'source':         'wise_csv',
            'notes':          notes,
        })

    return rows
