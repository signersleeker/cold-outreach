from __future__ import annotations

from app.lib.schemas import CamelModel


class InboxSyncSummaryDTO(CamelModel):
    scanned: int
    stops_found: int
    bounces_found: int
    soft_bounces: int
    auto_replies: int
    suppressed: int
    errors: list[str]
