"""Template industry and ordered template groups with delays."""

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


def test_group_keeps_template_order_and_delays(db: Session, template, follow_up_template) -> None:
    group = groups_service.create(
        db,
        name="CISO touches",
        items=[(follow_up_template.id, 0), (template.id, 5)],
    )
    assert [item.template_id for item in group.items] == [follow_up_template.id, template.id]
    assert [item.position for item in group.items] == [0, 1]
    assert [item.delay_days for item in group.items] == [0, 5]

    reordered = groups_service.update(
        db, group.id, items=[(template.id, 0), (follow_up_template.id, 3)]
    )
    assert [item.template_id for item in reordered.items] == [template.id, follow_up_template.id]
    assert [item.delay_days for item in reordered.items] == [0, 3]


def test_group_rejects_duplicates_and_missing_templates(db: Session, template) -> None:
    import uuid

    with pytest.raises(AppError) as duplicate:
        groups_service.create(
            db, name="Dupes", items=[(template.id, 0), (template.id, 3)]
        )
    assert duplicate.value.status_code == 400

    with pytest.raises(AppError) as missing:
        groups_service.create(db, name="Missing", items=[(uuid.uuid4(), 0)])
    assert missing.value.status_code == 404


def test_group_rejects_bad_delays(db: Session, template, follow_up_template) -> None:
    with pytest.raises(AppError) as first:
        groups_service.create(
            db, name="Bad first", items=[(template.id, 2), (follow_up_template.id, 3)]
        )
    assert first.value.status_code == 400

    with pytest.raises(AppError) as later:
        groups_service.create(
            db, name="Bad later", items=[(template.id, 0), (follow_up_template.id, 0)]
        )
    assert later.value.status_code == 400


def test_appending_a_template_keeps_existing_item_ids(
    db: Session, template, follow_up_template
) -> None:
    third = templates_service.create(
        db, name="Third", subject="s", body="Hi {{first_name}}"
    )
    group = groups_service.create(
        db, name="Stable", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    first_id = group.items[0].id
    second_id = group.items[1].id

    updated = groups_service.update(
        db,
        group.id,
        items=[(template.id, 0), (follow_up_template.id, 5), (third.id, 3)],
    )
    assert updated.items[0].id == first_id
    assert updated.items[1].id == second_id
    assert updated.items[2].template_id == third.id


def test_deleting_a_template_removes_it_from_the_group(
    db: Session, template, follow_up_template
) -> None:
    group = groups_service.create(
        db, name="Both", items=[(template.id, 0), (follow_up_template.id, 5)]
    )
    templates_service.delete(db, template.id)
    db.expire_all()
    reloaded = groups_service.require(db, group.id)
    assert [item.template_id for item in reloaded.items] == [follow_up_template.id]
