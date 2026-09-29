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


def match_industry(value: str) -> str | None:
    """Canonical industry, '' when blank, or None when the value is not in the list."""
    stripped = value.strip()
    if not stripped:
        return ""
    return _BY_LOWER.get(stripped.lower())


def require_industry(value: str) -> str:
    """Canonical industry, or '' when blank. Unknown values are an error."""
    matched = match_industry(value)
    if matched is None:
        raise AppError(400, f"unknown industry {value.strip()!r}")
    return matched
