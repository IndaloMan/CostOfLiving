"""
Company template manager.

Templates store known line item descriptions → categories for each company.
They are used to:
  1. Auto-fill categories on the review page for matching line items.
  2. Grow automatically whenever a receipt is confirmed — any categorised
     line item gets merged into the company's template.
"""

import json
from . import db
from .models import CompanyTemplate


def get_template_items(company_id: int) -> list:
    """Return the list of known {description, category} items for a company."""
    template = CompanyTemplate.query.filter_by(company_id=company_id).first()
    if not template or not template.known_items:
        return []
    try:
        return json.loads(template.known_items)
    except (ValueError, TypeError):
        return []


def apply_template_hints(line_items, template_items: list):
    """
    For each LineItem that has no category, look for a matching description
    in the template and apply its category.
    Works on ORM objects (with .description / .category attributes).
    Returns the same list, mutated in place.
    """
    if not template_items:
        return line_items

    for item in line_items:
        if item.category:
            continue  # already categorised — don't override
        matched = _find_match(item.description, template_items)
        if matched:
            item.category = matched

    return line_items


def update_template(company_id: int, line_items):
    """
    Merge confirmed line items into the company's template.
    - Items with no category are skipped.
    - Existing entries are updated if the category changed.
    - New items are appended.
    Caller must commit the session.
    """
    template = CompanyTemplate.query.filter_by(company_id=company_id).first()
    if not template:
        template = CompanyTemplate(company_id=company_id, known_items="[]")
        db.session.add(template)

    try:
        known = json.loads(template.known_items) if template.known_items else []
    except (ValueError, TypeError):
        known = []

    # Keyed by lowercase description for fast lookup
    known_dict = {entry["description"].lower(): entry for entry in known}

    for item in line_items:
        if not item.description or not item.category:
            continue
        key = item.description.lower()
        if key in known_dict:
            known_dict[key]["category"] = item.category  # update if changed
        else:
            known_dict[key] = {
                "description": item.description,
                "category": item.category,
            }

    template.known_items = json.dumps(list(known_dict.values()), ensure_ascii=False)
    db.session.flush()


def set_template_items(company_id: int, items: list):
    """
    Overwrite the template with a specific list of {description, category} dicts.
    Used by the manual edit UI.
    Caller must commit the session.
    """
    template = CompanyTemplate.query.filter_by(company_id=company_id).first()
    if not template:
        template = CompanyTemplate(company_id=company_id)
        db.session.add(template)

    template.known_items = json.dumps(items, ensure_ascii=False)
    db.session.flush()


# ---------------------------------------------------------------------------
# Internal matching
# ---------------------------------------------------------------------------

def _find_match(description: str, template_items: list):
    """
    Three-tier match (most specific first):
      1. Exact match (case-insensitive)
      2. Template description is a substring of the item description
      3. Item description is a substring of the template description
    """
    if not description:
        return None

    desc_lower = description.lower()

    for item in template_items:
        tmpl = item.get("description", "").lower()
        if tmpl == desc_lower:
            return item.get("category")

    for item in template_items:
        tmpl = item.get("description", "").lower()
        if tmpl and tmpl in desc_lower:
            return item.get("category")

    for item in template_items:
        tmpl = item.get("description", "").lower()
        if tmpl and desc_lower in tmpl:
            return item.get("category")

    return None
