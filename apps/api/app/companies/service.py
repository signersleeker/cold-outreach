from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.companies.company import Company
from app.contacts.contact import Contact
from app.lib.errors import AppError


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


def create(db: Session, name: str) -> Company:
    """Create a company explicitly. Refuses a blank or duplicate name."""
    stripped = name.strip()
    if not stripped:
        raise AppError(400, "a company name is required")
    existing = find_by_name(db, stripped)
    if existing is not None:
        raise AppError(409, f"{existing.name!r} already exists")
    company = Company(name=stripped[:200])
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
