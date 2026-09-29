from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response

from app.companies import service
from app.companies.schemas import CompanyCreateRequest, CompanyDetailDTO, CompanyDTO
from app.deps import DbSession
from app.lib.response import data_body, list_body

router = APIRouter(tags=["companies"])


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
                contact_count=count,
                created_at=company.created_at,
            )
            for company, count in rows
        ],
        {"total": total, "limit": limit, "offset": offset},
    )


@router.post("/companies")
def create_company(payload: CompanyCreateRequest, db: DbSession) -> Response:
    company = service.create(db, payload.name)
    return data_body(
        CompanyDetailDTO(
            id=company.id,
            name=company.name,
            created_at=company.created_at,
            updated_at=company.updated_at,
        ),
        status_code=201,
    )


@router.get("/companies/{company_id}")
def get_company(company_id: uuid.UUID, db: DbSession) -> Response:
    company = service.require(db, company_id)
    return data_body(
        CompanyDetailDTO(
            id=company.id,
            name=company.name,
            created_at=company.created_at,
            updated_at=company.updated_at,
        )
    )
