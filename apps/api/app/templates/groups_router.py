from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.deps import DbSession
from app.lib.response import data_body, list_body
from app.templates import groups
from app.templates.group import TemplateGroup
from app.templates.schemas import (
    TemplateGroupCreateRequest,
    TemplateGroupDTO,
    TemplateGroupItemDTO,
    TemplateGroupPatchRequest,
)

router = APIRouter(tags=["template-groups"])


def _to_dto(group: TemplateGroup) -> TemplateGroupDTO:
    items = [
        TemplateGroupItemDTO(
            position=item.position,
            template_id=item.template_id,
            template_name=item.template.name,
            subject=item.template.subject,
            industry=item.template.industry,
        )
        for item in group.items
        if item.template is not None
    ]
    return TemplateGroupDTO(
        id=group.id,
        name=group.name,
        items=items,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.get("/template-groups")
def list_groups(db: DbSession) -> Response:
    return list_body([_to_dto(group) for group in groups.list_all(db)])


@router.post("/template-groups")
def create_group(payload: TemplateGroupCreateRequest, db: DbSession) -> Response:
    group = groups.create(db, name=payload.name, template_ids=payload.template_ids)
    return data_body(_to_dto(group), status_code=201)


@router.get("/template-groups/{group_id}")
def get_group(group_id: uuid.UUID, db: DbSession) -> Response:
    return data_body(_to_dto(groups.require(db, group_id)))


@router.patch("/template-groups/{group_id}")
def patch_group(
    group_id: uuid.UUID, payload: TemplateGroupPatchRequest, db: DbSession
) -> Response:
    group = groups.update(
        db, group_id, name=payload.name, template_ids=payload.template_ids
    )
    return data_body(_to_dto(group))


@router.delete("/template-groups/{group_id}")
def delete_group(group_id: uuid.UUID, db: DbSession) -> Response:
    groups.delete(db, group_id)
    return data_body({"deleted": True})
