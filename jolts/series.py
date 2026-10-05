"""BLS JOLTS series definitions.

A JOLTS series ID has this layout (BLS "JT" survey):

    JT S 000000 00 00000 00 QU R
    |  | |      |  |     |  |  +-- R = rate (L = level, in thousands)
    |  | |      |  |     |  +----- data element: JO openings, HI hires, QU quits, LD layoffs & discharges
    |  | |      |  |     +-------- size class (00 = all sizes)
    |  | |      |  +-------------- area (00000 = all areas)
    |  | |      +----------------- state (00 = total US)
    |  | +------------------------ industry code
    |  +-------------------------- S = seasonally adjusted
    +----------------------------- survey prefix
"""

INDUSTRIES = {
    "000000": "Total nonfarm",
    "100000": "Total private",
    "110099": "Mining and logging",
    "230000": "Construction",
    "300000": "Manufacturing",
    "400000": "Trade, transportation and utilities",
    "510000": "Information",
    "510099": "Financial activities",
    "540099": "Professional and business services",
    "600000": "Education and health services",
    "700000": "Leisure and hospitality",
    "810000": "Other services",
    "900000": "Government",
}

# Short labels for charts.
SHORT_NAMES = {
    "000000": "Total nonfarm",
    "100000": "Total private",
    "110099": "Mining & logging",
    "230000": "Construction",
    "300000": "Manufacturing",
    "400000": "Trade, transp. & util.",
    "510000": "Information",
    "510099": "Financial activities",
    "540099": "Prof. & business svcs",
    "600000": "Education & health",
    "700000": "Leisure & hospitality",
    "810000": "Other services",
    "900000": "Government",
}

MEASURES = {
    "JO": "Job openings rate",
    "HI": "Hires rate",
    "QU": "Quits rate",
    "LD": "Layoffs and discharges rate",
}

# Total nonfarm and total private are roll-ups; the rest are the 11 sectors.
ROLLUPS = {"000000", "100000"}


def series_id(industry: str, measure: str) -> str:
    """Build a seasonally adjusted, national, all-sizes rate series ID."""
    if industry not in INDUSTRIES:
        raise ValueError(f"Unknown industry code: {industry}")
    if measure not in MEASURES:
        raise ValueError(f"Unknown measure: {measure}")
    return f"JTS{industry}000000000{measure}R"


def parse_series_id(sid: str) -> tuple[str, str]:
    """Return (industry_code, measure) from a series ID built by series_id()."""
    if len(sid) != 21 or not sid.startswith("JTS") or not sid.endswith("R"):
        raise ValueError(f"Not a national JOLTS rate series: {sid}")
    return sid[3:9], sid[18:20]


def all_series() -> list[str]:
    return [series_id(i, m) for i in INDUSTRIES for m in MEASURES]
