"""Named, ordered sets of templates with a delay after each previous send."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.lib.clock import Clock, SystemClock
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


def _normalize_items(
    items: list[tuple[uuid.UUID, int]],
) -> list[tuple[uuid.UUID, int]]:
    if not items:
        raise AppError(400, "a group needs at least one template")
    template_ids = [template_id for template_id, _ in items]
    if len(template_ids) != len(set(template_ids)):
        raise AppError(400, "a template can only appear once in a group")
    normalized: list[tuple[uuid.UUID, int]] = []
    for position, (template_id, delay_days) in enumerate(items):
        if position == 0:
            if delay_days != 0:
                raise AppError(400, "the first email is due immediately (delay must be 0)")
            normalized.append((template_id, 0))
            continue
        if delay_days < 1:
            raise AppError(400, "each follow-up needs a delay of at least 1 day")
        normalized.append((template_id, delay_days))
    return normalized


def _replace_items(
    db: Session, group: TemplateGroup, items: list[tuple[uuid.UUID, int]]
) -> None:
    """Update items in place so ids stay stable when a step is appended."""
    normalized = _normalize_items(items)
    template_ids = [template_id for template_id, _ in normalized]
    found = set(db.scalars(select(Template.id).where(Template.id.in_(template_ids))))
    if len(found) != len(template_ids):
        raise AppError(404, "template not found")

    existing_by_template = {item.template_id: item for item in list(group.items)}
    wanted = {template_id for template_id, _ in normalized}

    for item in list(group.items):
        if item.template_id not in wanted:
            group.items.remove(item)

    for position, (template_id, delay_days) in enumerate(normalized):
        current = existing_by_template.get(template_id)
        if current is not None and current in group.items:
            current.position = position
            current.delay_days = delay_days
            continue
        group.items.append(
            TemplateGroupItem(
                template_id=template_id, position=position, delay_days=delay_days
            )
        )
    db.flush()


def create(
    db: Session,
    *,
    name: str,
    items: list[tuple[uuid.UUID, int]],
    clock: Clock | None = None,
) -> TemplateGroup:
    stripped = name.strip()
    if not stripped:
        raise AppError(400, "a group name is required")
    if db.scalar(select(TemplateGroup.id).where(TemplateGroup.name == stripped)):
        raise AppError(409, f"a group named {stripped!r} already exists")
    group = TemplateGroup(name=stripped[:120])
    db.add(group)
    db.flush()
    _replace_items(db, group, items)
    db.commit()
    return require(db, group.id)


def update(
    db: Session,
    group_id: uuid.UUID,
    *,
    name: str | None = None,
    items: list[tuple[uuid.UUID, int]] | None = None,
    clock: Clock | None = None,
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
    if items is not None:
        _replace_items(db, group, items)
    group.updated_at = dt.datetime.now(dt.UTC)
    db.add(group)
    db.flush()
    if items is not None:
        from app.sequences import service as sequences_service

        sequences_service.reconcile_group(db, group, clock=clock or SystemClock())
    db.commit()
    return require(db, group.id)


def delete(db: Session, group_id: uuid.UUID) -> None:
    group = require(db, group_id)
    db.delete(group)
    db.commit()
