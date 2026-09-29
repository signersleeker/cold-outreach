"""Named, ordered sets of templates. A send is still one template, chosen by hand."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.lib.errors import AppError
from app.templates.group import TemplateGroup, TemplateGroupItem
from app.templates.template import Template


def list_all(db: Session) -> list[TemplateGroup]:
    return list(
        db.scalars(
            select(TemplateGroup)
            .options(selectinload(TemplateGroup.items).joinedload(TemplateGroupItem.template))
            .order_by(TemplateGroup.name)
        ).unique()
    )


def get(db: Session, group_id: uuid.UUID) -> TemplateGroup | None:
    return db.scalar(
        select(TemplateGroup)
        .options(selectinload(TemplateGroup.items).joinedload(TemplateGroupItem.template))
        .where(TemplateGroup.id == group_id)
    )


def require(db: Session, group_id: uuid.UUID) -> TemplateGroup:
    group = get(db, group_id)
    if group is None:
        raise AppError(404, "template group not found")
    return group


def _replace_items(db: Session, group: TemplateGroup, template_ids: list[uuid.UUID]) -> None:
    if not template_ids:
        raise AppError(400, "a group needs at least one template")
    if len(template_ids) != len(set(template_ids)):
        raise AppError(400, "a template can only appear once in a group")
    found = set(db.scalars(select(Template.id).where(Template.id.in_(template_ids))))
    if len(found) != len(template_ids):
        raise AppError(404, "template not found")
    group.items.clear()
    db.flush()
    for position, template_id in enumerate(template_ids):
        group.items.append(TemplateGroupItem(template_id=template_id, position=position))


def create(db: Session, *, name: str, template_ids: list[uuid.UUID]) -> TemplateGroup:
    stripped = name.strip()
    if not stripped:
        raise AppError(400, "a group name is required")
    if db.scalar(select(TemplateGroup.id).where(TemplateGroup.name == stripped)):
        raise AppError(409, f"a group named {stripped!r} already exists")
    group = TemplateGroup(name=stripped[:120])
    db.add(group)
    db.flush()
    _replace_items(db, group, template_ids)
    db.commit()
    return require(db, group.id)


def update(
    db: Session,
    group_id: uuid.UUID,
    *,
    name: str | None = None,
    template_ids: list[uuid.UUID] | None = None,
) -> TemplateGroup:
    group = require(db, group_id)
    if name is not None:
        stripped = name.strip()
        if not stripped:
            raise AppError(400, "a group name is required")
        existing = db.scalar(select(TemplateGroup.id).where(TemplateGroup.name == stripped))
        if existing is not None and existing != group.id:
            raise AppError(409, f"a group named {stripped!r} already exists")
        group.name = stripped[:120]
    if template_ids is not None:
        _replace_items(db, group, template_ids)
    group.updated_at = dt.datetime.now(dt.UTC)
    db.add(group)
    db.commit()
    return require(db, group.id)


def delete(db: Session, group_id: uuid.UUID) -> None:
    group = require(db, group_id)
    db.delete(group)
    db.commit()
