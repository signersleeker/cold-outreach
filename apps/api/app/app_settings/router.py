from __future__ import annotations

from fastapi import APIRouter, Response

from app.app_settings import service
from app.app_settings.app_setting import AppSetting
from app.app_settings.schemas import AppSettingsDTO, AppSettingsPatchRequest
from app.constants import HARD_MAX_DAILY_CAP, RECOMMENDED_DAILY_CAP
from app.deps import DbSession
from app.lib.response import data_body

router = APIRouter(tags=["settings"])


def _to_dto(row: AppSetting, effective_cap: int) -> AppSettingsDTO:
    return AppSettingsDTO(
        sender_name=row.sender_name,
        sender_title=row.sender_title,
        company_legal=row.company_legal,
        from_email=row.from_email,
        reply_hint=row.reply_hint,
        daily_cap=row.daily_cap,
        timezone=row.timezone,
        include_unsub_link=row.include_unsub_link,
        effective_daily_cap=effective_cap,
        hard_max_daily_cap=HARD_MAX_DAILY_CAP,
        recommended_daily_cap=RECOMMENDED_DAILY_CAP,
        last_inbox_sync_at=row.last_inbox_sync_at,
        updated_at=row.updated_at,
    )


@router.get("/settings")
def get_app_settings(db: DbSession) -> Response:
    row = service.get_or_create(db)
    db.commit()
    return data_body(_to_dto(row, service.effective_daily_cap(db)))


@router.patch("/settings")
def patch_app_settings(payload: AppSettingsPatchRequest, db: DbSession) -> Response:
    row = service.get_or_create(db)
    changes = payload.model_dump(exclude_none=True)
    if "timezone" in changes:
        changes["timezone"] = service.validate_timezone(changes["timezone"])
    for name, value in changes.items():
        setattr(row, name, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return data_body(_to_dto(row, service.effective_daily_cap(db)))
