# Company-specific analysers
ANALYSER_MAP = {
    "energy nordic": "electricity",
    "energía nórdica gas y electricidad s.l.u": "electricity",
    "energia nordica gas y electricidad s.l.u": "electricity",
    "energy nordic (energía nórdica gas y electricidad s.l.u)": "electricity",
}

# Maps known name aliases -> preferred display name stored in the DB
CANONICAL_NAMES = {
    "energía nórdica gas y electricidad s.l.u": "Energy Nordic",
    "energia nordica gas y electricidad s.l.u": "Energy Nordic",
    "energy nordic (energía nórdica gas y electricidad s.l.u)": "Energy Nordic",
}


def get_analyser_key(company_name: str, company_type: str = None):
    """Return the analyser module key for a company, or None."""
    if company_type == "Utility - Electric":
        return "electricity"
    return ANALYSER_MAP.get(company_name.lower().strip())


def canonical_name(company_name: str) -> str:
    """Return the canonical display name, or the original if not a known alias."""
    return CANONICAL_NAMES.get(company_name.lower().strip(), company_name)
