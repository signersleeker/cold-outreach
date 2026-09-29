"""Template industry and ordered template groups."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.lib.errors import AppError
from app.templates import groups as groups_service
from app.templates import service as templates_service


def test_template_industry_is_canonical(db: Session) -> None:
    template = templates_service.create(
        db,
        name="Insurers",
        subject="hello",
        body="Hi {{first_name}}",
        industry="insurance",
    )
    assert template.industry == "Insurance"

    cleared = templates_service.update(db, template.id, industry="")
    assert cleared.industry == ""

    with pytest.raises(AppError) as unknown:
        templates_service.create(
            db, name="Bad", subject="s", body="Hi {{first_name}}", industry="Space Mining"
        )
    assert unknown.value.status_code == 400


def test_group_keeps_template_order(db: Session, template, follow_up_template) -> None:
    group = groups_service.create(
        db,
        name="CISO touches",
        template_ids=[follow_up_template.id, template.id],
    )
    assert [item.template_id for item in group.items] == [follow_up_template.id, template.id]
    assert [item.position for item in group.items] == [0, 1]

    reordered = groups_service.update(
        db, group.id, template_ids=[template.id, follow_up_template.id]
    )
    assert [item.template_id for item in reordered.items] == [template.id, follow_up_template.id]


def test_group_rejects_duplicates_and_missing_templates(db: Session, template) -> None:
    import uuid

    with pytest.raises(AppError) as duplicate:
        groups_service.create(db, name="Dupes", template_ids=[template.id, template.id])
    assert duplicate.value.status_code == 400

    with pytest.raises(AppError) as missing:
        groups_service.create(db, name="Missing", template_ids=[uuid.uuid4()])
    assert missing.value.status_code == 404


def test_deleting_a_template_removes_it_from_the_group(
    db: Session, template, follow_up_template
) -> None:
    group = groups_service.create(
        db, name="Both", template_ids=[template.id, follow_up_template.id]
    )
    templates_service.delete(db, template.id)
    db.expire_all()
    reloaded = groups_service.require(db, group.id)
    assert [item.template_id for item in reloaded.items] == [follow_up_template.id]
