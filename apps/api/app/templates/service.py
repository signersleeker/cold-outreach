from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.companies.constants import require_industry
from app.lib.errors import AppError
from app.templates.template import Template


def list_all(db: Session) -> list[Template]:
    return list(db.scalars(select(Template).order_by(Template.name)))


def get(db: Session, template_id: uuid.UUID) -> Template | None:
    return db.get(Template, template_id)


def require(db: Session, template_id: uuid.UUID) -> Template:
    template = get(db, template_id)
    if template is None:
        raise AppError(404, "template not found")
    return template


def create(
    db: Session, *, name: str, subject: str, body: str, industry: str = ""
) -> Template:
    if db.scalar(select(Template).where(Template.name == name)):
        raise AppError(409, f"a template named {name!r} already exists")
    template = Template(name=name, subject=subject, body=body, industry=require_industry(industry))
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update(
    db: Session,
    template_id: uuid.UUID,
    *,
    name: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    industry: str | None = None,
) -> Template:
    template = require(db, template_id)
    if name is not None and name != template.name:
        if db.scalar(select(Template).where(Template.name == name)):
            raise AppError(409, f"a template named {name!r} already exists")
        template.name = name
    if subject is not None:
        template.subject = subject
    if body is not None:
        template.body = body
    if industry is not None:
        template.industry = require_industry(industry)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def delete(db: Session, template_id: uuid.UUID) -> None:
    """Delete a template. Send history survives via ON DELETE SET NULL."""
    template = require(db, template_id)
    db.delete(template)
    db.commit()
