"""Manual "Sync inbox" — find replies asking to stop, and hard bounces.

Operator-triggered, not a background scheduler and not Gmail push. Two bounded
query passes so one click cannot turn into hundreds of API calls.

The conservative choice here is deliberate: only a permanent (5.x.x) failure
suppresses. A deferral, an out-of-office, or a full mailbox is recorded and left
alone, because suppressing on a transient failure permanently burns a prospect
who did nothing wrong.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.contacts.contact import Contact
from app.gmail.client import GmailClient
from app.gmail.exceptions import GmailError
from app.inbox.parsing import Classification, classify_message
from app.lib.clock import Clock
from app.sends.constants import (
    SEND_STATUS_BOUNCED,
    SEND_STATUS_REPLIED_STOP,
    SEND_STATUS_SENT,
)
from app.sends.models.send_event import SendEvent
from app.suppressions import service as suppressions_service
from app.suppressions.constants import REASON_BOUNCE, REASON_REPLY_NO

# Gmail rejects very long queries, so contact addresses are batched.
_ADDRESSES_PER_QUERY = 25
_MAX_MESSAGES_PER_PASS = 100
_REPLY_WINDOW_DAYS = 30
_BOUNCE_WINDOW_DAYS = 14

_BOUNCE_QUERY = (
    f"in:anywhere newer_than:{_BOUNCE_WINDOW_DAYS}d "
    "(from:mailer-daemon OR from:postmaster "
    'OR subject:"Delivery Status Notification" '
    'OR subject:"Undelivered Mail Returned to Sender" '
    'OR subject:"Undeliverable")'
)


@dataclass
class SyncSummary:
    scanned: int = 0
    stops_found: int = 0
    bounces_found: int = 0
    soft_bounces: int = 0
    auto_replies: int = 0
    suppressed: int = 0
    errors: list[str] = field(default_factory=list)


class InboxSyncService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def sync(self, db: Session, client: GmailClient) -> SyncSummary:
        summary = SyncSummary()
        now = self.clock.now()

        known = self._known_contact_emails(db)
        queries = [_BOUNCE_QUERY, *self._reply_queries(known)]

        seen: set[str] = set()
        for query in queries:
            try:
                message_ids = client.list_message_ids(query, max_results=_MAX_MESSAGES_PER_PASS)
            except GmailError as exc:
                summary.errors.append(f"list failed: {exc}")
                continue

            for message_id in message_ids:
                if message_id in seen:
                    continue
                seen.add(message_id)
                try:
                    payload = client.get_message(message_id).get("payload") or {}
                except GmailError as exc:
                    summary.errors.append(f"read {message_id} failed: {exc}")
                    continue

                summary.scanned += 1
                self._handle(db, classify_message(payload), known, summary, now)

        settings_service.get_or_create(db).last_inbox_sync_at = now
        db.commit()
        return summary

    # ------------------------------------------------------------ internal ----
    def _known_contact_emails(self, db: Session) -> set[str]:
        cutoff = self.clock.now() - dt.timedelta(days=_REPLY_WINDOW_DAYS)
        return set(
            db.scalars(
                select(Contact.email).where(
                    Contact.last_sent_at.is_not(None), Contact.last_sent_at >= cutoff
                )
            )
        )

    def _reply_queries(self, known: set[str]) -> list[str]:
        addresses = sorted(known)
        queries: list[str] = []
        for start in range(0, len(addresses), _ADDRESSES_PER_QUERY):
            chunk = addresses[start : start + _ADDRESSES_PER_QUERY]
            joined = " OR ".join(f"from:{address}" for address in chunk)
            queries.append(f"in:inbox newer_than:{_REPLY_WINDOW_DAYS}d ({joined})")
        return queries

    def _handle(
        self,
        db: Session,
        parsed,  # noqa: ANN001 - ParsedMessage, imported lazily to keep parsing pure
        known: set[str],
        summary: SyncSummary,
        now: dt.datetime,
    ) -> None:
        if parsed.classification is Classification.REPLY_STOP:
            if parsed.from_email not in known:
                return
            summary.stops_found += 1
            suppressions_service.suppress(
                db,
                parsed.from_email,
                reason=REASON_REPLY_NO,
                source=f"inbox sync: {parsed.detail}"[:200],
                now=now,
            )
            summary.suppressed += 1
            self._mark_latest_send(db, parsed.from_email, SEND_STATUS_REPLIED_STOP, parsed.detail)
            return

        if parsed.classification is Classification.BOUNCE_PERMANENT:
            target = parsed.affected_email or ""
            if not target or target not in known:
                return
            summary.bounces_found += 1
            suppressions_service.suppress(
                db,
                target,
                reason=REASON_BOUNCE,
                source=f"inbox sync: {parsed.detail}"[:200],
                now=now,
            )
            summary.suppressed += 1
            self._mark_latest_send(db, target, SEND_STATUS_BOUNCED, parsed.detail)
            return

        if parsed.classification is Classification.BOUNCE_SOFT:
            # Recorded, never suppressed.
            summary.soft_bounces += 1
            if parsed.affected_email:
                self._annotate_latest_send(db, parsed.affected_email, parsed.detail)
            return

        if parsed.classification is Classification.AUTO_REPLY:
            summary.auto_replies += 1

    def _latest_send(self, db: Session, email: str) -> SendEvent | None:
        contact = db.scalar(select(Contact).where(Contact.email == email.lower()))
        if contact is None:
            return None
        return db.scalar(
            select(SendEvent)
            .where(SendEvent.contact_id == contact.id, SendEvent.status == SEND_STATUS_SENT)
            .order_by(SendEvent.created_at.desc())
            .limit(1)
        )

    def _mark_latest_send(self, db: Session, email: str, status: str, detail: str) -> None:
        """Reflect the outcome on the most recent successful send.

        A stop reply is a fact about a contact, not about one specific message, so
        this is a convenience for the send history. The suppression row is the
        authoritative record.
        """
        event = self._latest_send(db, email)
        if event is None:
            return
        event.status = status
        event.error = detail[:1000]
        db.add(event)

    def _annotate_latest_send(self, db: Session, email: str, detail: str) -> None:
        event = self._latest_send(db, email)
        if event is None:
            return
        event.error = detail[:1000]
        db.add(event)
