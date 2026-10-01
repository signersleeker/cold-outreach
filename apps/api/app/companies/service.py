from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.companies.company import Company
from app.companies.constants import match_industry, match_size, require_industry, require_size
from app.contacts.contact import Contact
from app.lib.errors import AppError


def _website(value: str) -> str:
    return value.strip()[:500]


def _location(value: str) -> str:
    return value.strip()[:200]


def get(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.get(Company, company_id)


def require(db: Session, company_id: uuid.UUID) -> Company:
    company = get(db, company_id)
    if company is None:
        raise AppError(404, "company not found")
    return company


def find_by_name(db: Session, name: str) -> Company | None:
    stripped = name.strip()
    if not stripped:
        return None
    return db.scalar(select(Company).where(func.lower(Company.name) == stripped.lower()))


def fill_blanks(
    company: Company,
    *,
    website: str = "",
    linkedin_url: str = "",
    industry: str = "",
    size: str = "",
    location: str = "",
) -> None:
    """Set profile fields only where the company does not already have a value.

    An unrecognised industry or size is ignored so a bad CSV cell does not fail the row.
    """
    site = _website(website)
    if site and not company.website:
        company.website = site
    linkedin = _website(linkedin_url)
    if linkedin and not company.linkedin_url:
        company.linkedin_url = linkedin
    if not company.industry:
        matched = match_industry(industry)
        if matched:
            company.industry = matched
    if not company.size:
        matched_size = match_size(size)
        if matched_size:
            company.size = matched_size
    place = _location(location)
    if place and not company.location:
        company.location = place


def find_or_create(db: Session, name: str) -> Company | None:
    """Return an existing company for this name, or create one.

    Blank names yield None. Matching is case-insensitive; the first spelling seen
    is the one stored.
    """
    stripped = name.strip()
    if not stripped:
        return None
    existing = find_by_name(db, stripped)
    if existing is not None:
        return existing
    company = Company(name=stripped[:200])
    db.add(company)
    db.flush()
    return company


def create(
    db: Session,
    name: str,
    *,
    website: str = "",
    linkedin_url: str = "",
    industry: str = "",
    size: str = "",
    location: str = "",
) -> Company:
    """Create a company explicitly. Refuses a blank or duplicate name."""
    stripped = name.strip()
    if not stripped:
        raise AppError(400, "a company name is required")
    existing = find_by_name(db, stripped)
    if existing is not None:
        raise AppError(409, f"{existing.name!r} already exists")
    company = Company(
        name=stripped[:200],
        website=_website(website),
        linkedin_url=_website(linkedin_url),
        industry=require_industry(industry),
        size=require_size(size),
        location=_location(location),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def update(
    db: Session,
    company_id: uuid.UUID,
    *,
    name: str | None = None,
    website: str | None = None,
    linkedin_url: str | None = None,
    industry: str | None = None,
    size: str | None = None,
    location: str | None = None,
) -> Company:
    company = require(db, company_id)
    if name is not None:
        stripped = name.strip()
        if not stripped:
            raise AppError(400, "a company name is required")
        existing = find_by_name(db, stripped)
        if existing is not None and existing.id != company.id:
            raise AppError(409, f"{existing.name!r} already exists")
        company.name = stripped[:200]
    if website is not None:
        company.website = _website(website)
    if linkedin_url is not None:
        company.linkedin_url = _website(linkedin_url)
    if industry is not None:
        company.industry = require_industry(industry)
    if size is not None:
        company.size = require_size(size)
    if location is not None:
        company.location = _location(location)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def search(
    db: Session,
    *,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Company, int]], int]:
    """Return (company, contact_count) rows ordered by name."""
    count_expr = func.count(Contact.id)
    query = (
        select(Company, count_expr)
        .outerjoin(Contact, Contact.company_id == Company.id)
        .group_by(Company.id)
    )
    count_query = select(func.count()).select_from(Company)

    if q.strip():
        pattern = f"%{q.strip().lower()}%"
        query = query.where(func.lower(Company.name).like(pattern))
        count_query = count_query.where(func.lower(Company.name).like(pattern))

    total = db.scalar(count_query) or 0
    rows = list(
        db.execute(query.order_by(func.lower(Company.name)).limit(limit).offset(offset)).all()
    )
    return [(company, int(n)) for company, n in rows], total
