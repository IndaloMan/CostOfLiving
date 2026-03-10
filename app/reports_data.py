"""
Report data queries — all return plain dicts/lists ready for JSON serialisation.
Uses Python-level grouping for date periods so it works cleanly with SQLite.
"""

from datetime import date, timedelta
from . import db
from .models import Receipt, LineItem, Company
from sqlalchemy import func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_date(val, default: date) -> date:
    if not val:
        return default
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return default


def default_start() -> date:
    today = date.today()
    return today.replace(year=today.year - 1)


def _period_key(d: date, group_by: str) -> str:
    if group_by == "year":
        return str(d.year)
    if group_by == "quarter":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    return f"{d.year}-{d.month:02d}"  # month (default)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _company_filter(query, company_id):
    """Append a company_id filter to a query if one is specified."""
    if company_id:
        query = query.filter(Receipt.company_id == company_id)
    return query


def get_summary(start: date, end: date, company_id: int = None) -> dict:
    """Total spend, receipt count, average, and top category for the period."""
    row = (
        _company_filter(
            db.session.query(
                func.sum(Receipt.total_amount).label("total"),
                func.count(Receipt.id).label("count"),
            )
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
            ),
            company_id,
        )
        .first()
    )

    total = float(row.total or 0)
    count = int(row.count or 0)

    top_cat = (
        _company_filter(
            db.session.query(
                LineItem.category,
                func.sum(LineItem.total_price).label("cat_total"),
            )
            .join(Receipt, LineItem.receipt_id == Receipt.id)
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
                LineItem.category.isnot(None),
                LineItem.category != "",
                LineItem.total_price.isnot(None),
            ),
            company_id,
        )
        .group_by(LineItem.category)
        .order_by(func.sum(LineItem.total_price).desc())
        .first()
    )

    return {
        "total_spent": round(total, 2),
        "receipt_count": count,
        "avg_per_receipt": round(total / count, 2) if count else 0,
        "top_category": top_cat.category if top_cat else "—",
    }


# ---------------------------------------------------------------------------
# Spending over time
# ---------------------------------------------------------------------------

def get_spending_over_time(start: date, end: date, group_by: str = "month", company_id: int = None) -> dict:
    """Total spending grouped by month / quarter / year."""
    rows = (
        _company_filter(
            db.session.query(Receipt.receipt_date, Receipt.total_amount)
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
                Receipt.total_amount.isnot(None),
                Receipt.receipt_date.isnot(None),
            ),
            company_id,
        )
        .order_by(Receipt.receipt_date)
        .all()
    )

    groups: dict[str, float] = {}
    for r in rows:
        key = _period_key(r.receipt_date, group_by)
        groups[key] = groups.get(key, 0.0) + float(r.total_amount)

    sorted_keys = sorted(groups)
    return {
        "labels": sorted_keys,
        "values": [round(groups[k], 2) for k in sorted_keys],
    }


# ---------------------------------------------------------------------------
# By category
# ---------------------------------------------------------------------------

def get_by_category(start: date, end: date, company_id: int = None) -> dict:
    """Total spending per category, highest first."""
    rows = (
        _company_filter(
            db.session.query(
                LineItem.category,
                func.sum(LineItem.total_price).label("total"),
            )
            .join(Receipt, LineItem.receipt_id == Receipt.id)
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
                LineItem.category.isnot(None),
                LineItem.category != "",
                LineItem.total_price.isnot(None),
            ),
            company_id,
        )
        .group_by(LineItem.category)
        .order_by(func.sum(LineItem.total_price).desc())
        .all()
    )

    return {
        "labels": [r.category for r in rows],
        "values": [round(float(r.total), 2) for r in rows],
    }


# ---------------------------------------------------------------------------
# By company
# ---------------------------------------------------------------------------

def get_by_company(start: date, end: date, limit: int = 10, company_id: int = None) -> dict:
    """Total spending per company, highest first."""
    rows = (
        _company_filter(
            db.session.query(
                Company.name,
                func.sum(Receipt.total_amount).label("total"),
            )
            .join(Company, Receipt.company_id == Company.id)
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
                Receipt.total_amount.isnot(None),
            ),
            company_id,
        )
        .group_by(Company.name)
        .order_by(func.sum(Receipt.total_amount).desc())
        .limit(limit)
        .all()
    )

    return {
        "labels": [r.name for r in rows],
        "values": [round(float(r.total), 2) for r in rows],
    }


# ---------------------------------------------------------------------------
# Price trend
# ---------------------------------------------------------------------------

def get_price_trend(description: str, start: date, end: date, company_id: int = None) -> dict:
    """
    Unit price of a line item (matched by partial description) over time.
    Uses unit_price if set; otherwise total_price / quantity.
    """
    rows = (
        _company_filter(
            db.session.query(
                Receipt.receipt_date,
                LineItem.description,
                LineItem.unit_price,
                LineItem.total_price,
                LineItem.quantity,
            )
            .join(Receipt, LineItem.receipt_id == Receipt.id)
            .filter(
                Receipt.status == "confirmed",
                Receipt.receipt_date >= start,
                Receipt.receipt_date <= end,
                LineItem.description.ilike(f"%{description}%"),
            ),
            company_id,
        )
        .order_by(Receipt.receipt_date)
        .all()
    )

    points = []
    for r in rows:
        if r.unit_price is not None:
            price = float(r.unit_price)
        elif r.total_price is not None and r.quantity:
            price = float(r.total_price) / float(r.quantity)
        else:
            continue
        points.append({"date": r.receipt_date.isoformat(), "price": round(price, 3)})

    return {
        "labels": [p["date"] for p in points],
        "values": [p["price"] for p in points],
        "description": description,
    }


# ---------------------------------------------------------------------------
# Spend per visit (one data point per receipt)
# ---------------------------------------------------------------------------

def get_spend_per_visit(start: date, end: date, company_id: int) -> dict:
    """Return each confirmed receipt as a labelled data point — used for basket-size charts."""
    rows = (
        db.session.query(Receipt.receipt_date, Receipt.total_amount, Receipt.id)
        .filter(
            Receipt.status == "confirmed",
            Receipt.company_id == company_id,
            Receipt.receipt_date >= start,
            Receipt.receipt_date <= end,
            Receipt.total_amount.isnot(None),
            Receipt.receipt_date.isnot(None),
        )
        .order_by(Receipt.receipt_date)
        .all()
    )
    return {
        "labels": [r.receipt_date.isoformat() for r in rows],
        "values": [round(float(r.total_amount), 2) for r in rows],
    }


# ---------------------------------------------------------------------------
# Top items by total spend
# ---------------------------------------------------------------------------

def get_top_items(start: date, end: date, company_id: int, limit: int = 15) -> dict:
    """Most purchased items ranked by total spend, with purchase count and avg unit price."""
    rows = (
        db.session.query(
            LineItem.description,
            func.count(LineItem.id).label("purchase_count"),
            func.sum(LineItem.total_price).label("total_spent"),
            func.avg(LineItem.unit_price).label("avg_unit_price"),
        )
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .filter(
            Receipt.status == "confirmed",
            Receipt.company_id == company_id,
            Receipt.receipt_date >= start,
            Receipt.receipt_date <= end,
            LineItem.total_price.isnot(None),
        )
        .group_by(func.lower(LineItem.description))
        .order_by(func.sum(LineItem.total_price).desc())
        .limit(limit)
        .all()
    )
    return {
        "labels":         [r.description for r in rows],
        "total_spent":    [round(float(r.total_spent), 2) for r in rows],
        "purchase_count": [int(r.purchase_count) for r in rows],
        "avg_unit_price": [round(float(r.avg_unit_price), 2) if r.avg_unit_price else None for r in rows],
    }


# ---------------------------------------------------------------------------
# Item autocomplete suggestions
# ---------------------------------------------------------------------------

def get_item_suggestions(q: str, limit: int = 12, company_id: int = None) -> list:
    """Return distinct item descriptions matching a search string, most frequent first."""
    query = (
        db.session.query(LineItem.description)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .filter(LineItem.description.ilike(f"%{q}%"))
    )
    if company_id:
        query = query.filter(Receipt.company_id == company_id)
    rows = (
        query
        .group_by(func.lower(LineItem.description))
        .order_by(func.count(LineItem.id).desc())
        .limit(limit)
        .all()
    )
    return [r.description for r in rows]


# ---------------------------------------------------------------------------
# Item analysis (supermarkets)
# ---------------------------------------------------------------------------

def get_item_analysis(start: date, end: date, company_id: int = None) -> list:
    """Return per-item stats (qty, price low/high) for supermarket receipts."""
    query = (
        db.session.query(
            LineItem.description,
            func.min(LineItem.category).label('category'),
            func.count(LineItem.receipt_id.distinct()).label('qty'),
            func.min(LineItem.unit_price).label('price_low'),
            func.max(LineItem.unit_price).label('price_high'),
        )
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .join(Company, Receipt.company_id == Company.id)
        .filter(Company.type == 'Supermarket')
        .filter(Receipt.receipt_date >= start, Receipt.receipt_date <= end)
    )
    if company_id:
        query = query.filter(Company.id == company_id)
    rows = (
        query
        .group_by(func.lower(LineItem.description))
        .order_by(LineItem.description)
        .all()
    )
    result = []
    for row in rows:
        low  = round(float(row.price_low),  4) if row.price_low  is not None else None
        high = round(float(row.price_high), 4) if row.price_high is not None else None
        if low and high and low != 0:
            pct_diff = round((high - low) / low * 100, 1)
        else:
            pct_diff = None
        result.append({
            'description': row.description,
            'category':    row.category or '',
            'qty':         row.qty,
            'price_low':   low,
            'price_high':  high,
            'pct_diff':    pct_diff,
        })
    return result

# ---------------------------------------------------------------------------
# Income vs Expenses report
# ---------------------------------------------------------------------------

def get_income_report(start: date, end: date) -> dict:
    """Monthly income vs expenses, net balance, and account opening balance summary."""
    from .models import Income, Account

    income_rows = (
        Income.query
        .filter(Income.date >= start, Income.date <= end)
        .order_by(Income.date)
        .all()
    )

    expense_rows = (
        db.session.query(Receipt.receipt_date, Receipt.total_amount)
        .filter(
            Receipt.status == "confirmed",
            Receipt.receipt_date >= start,
            Receipt.receipt_date <= end,
            Receipt.total_amount.isnot(None),
            Receipt.receipt_date.isnot(None),
        )
        .order_by(Receipt.receipt_date)
        .all()
    )

    income_by_month: dict[str, float] = {}
    for r in income_rows:
        key = f"{r.date.year}-{r.date.month:02d}"
        income_by_month[key] = income_by_month.get(key, 0.0) + float(r.amount)

    expense_by_month: dict[str, float] = {}
    for r in expense_rows:
        key = f"{r.receipt_date.year}-{r.receipt_date.month:02d}"
        expense_by_month[key] = expense_by_month.get(key, 0.0) + float(r.total_amount)

    all_keys = sorted(set(list(income_by_month.keys()) + list(expense_by_month.keys())))
    income_vals   = [round(income_by_month.get(k, 0.0),  2) for k in all_keys]
    expense_vals  = [round(expense_by_month.get(k, 0.0), 2) for k in all_keys]
    net_vals      = [round(i - e, 2) for i, e in zip(income_vals, expense_vals)]

    total_income   = round(sum(income_vals),  2)
    total_expenses = round(sum(expense_vals), 2)
    net            = round(total_income - total_expenses, 2)

    accounts = Account.query.order_by(Account.name).all()
    total_assets      = round(sum(a.opening_balance for a in accounts if a.opening_balance > 0), 2)
    total_liabilities = round(sum(a.opening_balance for a in accounts if a.opening_balance < 0), 2)
    net_worth         = round(sum(a.opening_balance for a in accounts), 2)

    return {
        "labels":   all_keys,
        "income":   income_vals,
        "expenses": expense_vals,
        "net":      net_vals,
        "summary": {
            "total_income":   total_income,
            "total_expenses": total_expenses,
            "net":            net,
        },
        "accounts": {
            "total_assets":      total_assets,
            "total_liabilities": total_liabilities,
            "net_worth":         net_worth,
        },
    }

