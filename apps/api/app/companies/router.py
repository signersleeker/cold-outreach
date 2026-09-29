from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response

from app.companies import service
from app.companies.company import Company
from app.companies.schemas import (
    CompanyCreateRequest,
    CompanyDetailDTO,
    CompanyDTO,
    CompanyPatchRequest,
)
from app.deps import DbSession
from app.lib.response import data_body, list_body

router = APIRouter(tags=["companies"])


def _detail(company: Company) -> CompanyDetailDTO:
    return CompanyDetailDTO(
        id=company.id,
        name=company.name,
        website=company.website,
        industry=company.industry,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.get("/companies")
def list_companies(
    db: DbSession,
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Response:
    rows, total = service.search(db, q=q, limit=limit, offset=offset)
    return list_body(
        [
            CompanyDTO(
                id=company.id,
                name=company.name,
                website=company.website,
                industry=company.industry,
                contact_count=count,
                created_at=company.created_at,
            )
            for company, count in rows
        ],
        {"total": total, "limit": limit, "offset": offset},
    )


@router.post("/companies")
def create_company(payload: CompanyCreateRequest, db: DbSession) -> Response:
    company = service.create(
        db, payload.name, website=payload.website, industry=payload.industry
    )
    return data_body(_detail(company), status_code=201)


@router.get("/companies/{company_id}")
def get_company(company_id: uuid.UUID, db: DbSession) -> Response:
    return data_body(_detail(service.require(db, company_id)))


@router.patch("/companies/{company_id}")
def patch_company(
    company_id: uuid.UUID, payload: CompanyPatchRequest, db: DbSession
) -> Response:
    company = service.update(
        db,
        company_id,
        name=payload.name,
        website=payload.website,
        industry=payload.industry,
    )
    return data_body(_detail(company))
