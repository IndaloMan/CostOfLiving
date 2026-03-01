# Company-specific analysers
ANALYSER_MAP = {
    "energy nordic": "energy_nordic",
    "energía nórdica gas y electricidad s.l.u": "energy_nordic",
    "energia nordica gas y electricidad s.l.u": "energy_nordic",
    "energy nordic (energía nórdica gas y electricidad s.l.u)": "energy_nordic",
}

# Maps known aliases to the preferred display name stored in the DB
CANONICAL_NAMES = {
    "energía nórdica gas y electricidad s.l.u": "Energy Nordic",
    "energia nordica gas y electricidad s.l.u": "Energy Nordic",
    "energy nordic (energía nórdica gas y electricidad s.l.u)": "Energy Nordic",
}


def get_analyser_key(company_name: str):
    """Return the analyser module key for a company name, or None."""
    return ANALYSER_MAP.get(company_name.lower().strip())


def canonical_name(company_name: str) -> str:
    """Return the canonical display name, or the original if not a known alias."""
    return CANONICAL_NAMES.get(company_name.lower().strip(), company_name)
