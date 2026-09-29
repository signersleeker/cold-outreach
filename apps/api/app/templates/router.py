from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from app.deps import DbSession
from app.lib.response import data_body, list_body
from app.templates import service
from app.templates.render import referenced_vars, unknown_vars
from app.templates.schemas import (
    TemplateCreateRequest,
    TemplatePatchRequest,
    TemplateWithVarsDTO,
)
from app.templates.template import Template

router = APIRouter(tags=["templates"])


def _to_dto(template: Template) -> TemplateWithVarsDTO:
    return TemplateWithVarsDTO(
        id=template.id,
        name=template.name,
        subject=template.subject,
        body=template.body,
        industry=template.industry,
        created_at=template.created_at,
        updated_at=template.updated_at,
        referenced_vars=list(referenced_vars(template.subject, template.body)),
        unknown_vars=list(unknown_vars(template.subject, template.body)),
    )


@router.get("/templates")
def list_templates(db: DbSession) -> Response:
    return list_body([_to_dto(t) for t in service.list_all(db)])


@router.post("/templates")
def create_template(payload: TemplateCreateRequest, db: DbSession) -> Response:
    template = service.create(
        db,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        industry=payload.industry,
    )
    return data_body(_to_dto(template), status_code=201)


@router.get("/templates/{template_id}")
def get_template(template_id: uuid.UUID, db: DbSession) -> Response:
    return data_body(_to_dto(service.require(db, template_id)))


@router.patch("/templates/{template_id}")
def patch_template(
    template_id: uuid.UUID, payload: TemplatePatchRequest, db: DbSession
) -> Response:
    template = service.update(
        db,
        template_id,
        name=payload.name,
        subject=payload.subject,
        body=payload.body,
        industry=payload.industry,
    )
    return data_body(_to_dto(template))


@router.delete("/templates/{template_id}")
def delete_template(template_id: uuid.UUID, db: DbSession) -> Response:
    service.delete(db, template_id)
    return data_body({"deleted": True})
