"""Industries a company or template can be tagged with.

Blank means unset. Anything else must match this list (case-insensitive);
the stored value is always the canonical spelling.
"""

from __future__ import annotations

from app.lib.errors import AppError

INDUSTRIES: tuple[str, ...] = (
    "Information Technology",
    "Telecommunications",
    "Hardware & Electronics",
    "Financial Services",
    "Insurance",
    "Professional Services",
    "Legal",
    "Healthcare Services",
    "Pharmaceuticals & Biotechnology",
    "Medical Devices",
    "Retail Trade",
    "Food & Beverage",
    "Apparel & Cosmetics",
    "Construction",
    "Manufacturing",
    "Logistics & Transportation",
    "Mining & Metals",
    "Utilities",
)

_BY_LOWER = {name.lower(): name for name in INDUSTRIES}

# Employee-count buckets. Blank means unset. Stored value is always canonical.
COMPANY_SIZES: tuple[str, ...] = (
    "1-10",
    "11-25",
    "26-50",
    "51-100",
    "101-200",
    "201-500",
    "501-1000",
    "1001-5000",
    "5000+",
)


def _fold_size(value: str) -> str:
    """Compare key: drop spaces and a trailing 'employees', and flatten dashes."""
    folded = value.strip().lower().replace("–", "-").replace("—", "-")
    if folded.endswith(" employees"):
        folded = folded[: -len(" employees")]
    elif folded.endswith(" employee"):
        folded = folded[: -len(" employee")]
    return "".join(folded.split())


_SIZE_BY_FOLDED = {_fold_size(size): size for size in COMPANY_SIZES}

# Query value for "no industry": a contact with no company, or a company left blank.
# Not a member of INDUSTRIES, so it cannot collide with a stored tag.
UNSET_INDUSTRY = "none"


def match_industry(value: str) -> str | None:
    """Canonical industry, '' when blank, or None when the value is not in the list."""
    stripped = value.strip()
    if not stripped:
        return ""
    return _BY_LOWER.get(stripped.lower())


def match_size(value: str) -> str | None:
    """Canonical company size, '' when blank, or None when the value is not a bucket."""
    if not value.strip():
        return ""
    return _SIZE_BY_FOLDED.get(_fold_size(value))


def require_size(value: str) -> str:
    """Canonical company size, or '' when blank. Unknown values are an error."""
    matched = match_size(value)
    if matched is None:
        raise AppError(400, f"unknown company size {value.strip()!r}")
    return matched


def require_industry(value: str) -> str:
    """Canonical industry, or '' when blank. Unknown values are an error."""
    matched = match_industry(value)
    if matched is None:
        raise AppError(400, f"unknown industry {value.strip()!r}")
    return matched


def resolve_industry_filter(value: str) -> str | None:
    """Industry scope for a contact list.

    None means the filter is off. '' means contacts with no industry. A
    canonical name matches that industry. Matching is case-insensitive.
    """
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.lower() == UNSET_INDUSTRY:
        return ""
    matched = match_industry(stripped)
    if not matched:
        raise AppError(400, f"unknown industry {stripped!r}")
    return matched
