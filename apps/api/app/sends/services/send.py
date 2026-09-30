"""Preview and send. The transaction choreography lives here.

The Gmail call is irreversible and non-transactional; the database is
transactional. They cannot be made atomic, so the design picks a failure bias,
and for a spam cap it must be fail-closed: never over-send, accept occasionally
under-sending.

    TX1   reserve slot + record intent      commit
    ----  Gmail users.messages.send         (irreversible side effect)
    TX2   settle, or release + mark failed  commit

Three details make an interruption survivable:

1. The slot and a durable send_events row exist *before* the irreversible act, so
   a crash mid-send leaves a `queued` row and a consumed slot. The cap is never
   exceeded.
2. contacts.last_sent_at is written in TX1, not TX2, so a permanent Gmail failure
   can roll it back with the reserved slot, and the contact stays marked contacted
   if the outcome is ambiguous.
3. The RFC 822 Message-ID is generated and persisted before the call, so
   app/cli/reconcile_sends.py can later discover the true outcome.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.config import Settings
from app.contacts.contact import Contact
from app.gmail.client import GmailClient
from app.gmail.exceptions import GmailAmbiguousError, GmailPermanentError
from app.gmail.mime import build_outbound_message, encode_raw, new_message_id
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock, local_date
from app.lib.errors import AppError
from app.sends.constants import (
    SEND_STATUS_FAILED,
    SEND_STATUS_QUEUED,
    SEND_STATUS_SENT,
)
from app.sends.gates import GateResult, evaluate_gates
from app.sends.models.send_event import SendEvent
from app.sends.services import counters
from app.sends.services.gate_input import collect


@dataclass(frozen=True)
class SendPreview:
    subject: str
    body: str
    body_html: str
    signature_html: str
    unsub_url: str
    from_email: str
    sends_today: int
    daily_cap: int
    result: GateResult


class SendService:
    def __init__(
        self,
        *,
        settings: Settings,
        oauth: GmailOAuthService,
        clock: Clock,
        client_factory: object | None = None,
    ) -> None:
        self.settings = settings
        self.oauth = oauth
        self.clock = clock
        # Overridden in tests with a fake; None means "use the real OAuth client".
        self._client_factory = client_factory

    def _client(self, db: Session) -> GmailClient:
        if self._client_factory is not None:
            return self._client_factory(db)  # type: ignore[operator]
        return self.oauth.client(db)

    # ------------------------------------------------------------- preview ----
    def preview(
        self,
        db: Session,
        *,
        contact_id: uuid.UUID,
        template_id: uuid.UUID,
        acknowledge: frozenset[str] = frozenset(),
        assumed_sends_today: int | None = None,
    ) -> SendPreview:
        contact = db.get(Contact, contact_id)
        if contact is None:
            raise AppError(404, "contact not found")

        gmail_client = None
        if self._client_factory is not None or self.oauth.is_connected(db):
            try:
                gmail_client = self._client(db)
            except RuntimeError:
                gmail_client = None

        collected = collect(
            db,
            contact=contact,
            template_id=template_id,
            settings=self.settings,
            oauth=self.oauth,
            clock=self.clock,
            acknowledge=acknowledge,
            client=gmail_client,
        )
        gate_input = collected.gate_input
        if assumed_sends_today is not None:
            gate_input = replace(gate_input, sends_today=assumed_sends_today)
        return SendPreview(
            subject=collected.subject,
            body=collected.final_body,
            body_html=collected.body_html,
            signature_html=collected.signature_html,
            unsub_url=collected.unsub_url,
            from_email=collected.from_email,
            sends_today=gate_input.sends_today,
            daily_cap=gate_input.daily_cap,
            result=evaluate_gates(gate_input),
        )

    # ---------------------------------------------------------------- send ----
    def send(
        self,
        db: Session,
        *,
        contact_id: uuid.UUID,
        template_id: uuid.UUID,
        acknowledge: frozenset[str] = frozenset(),
    ) -> SendEvent:
        day = local_date(self.clock, settings_service.effective_timezone(db))

        # ---------------------------- TX1: reserve ----------------------------
        # FOR UPDATE first: the lock is what serialises two concurrent sends to
        # the same contact.
        contact = db.scalar(select(Contact).where(Contact.id == contact_id).with_for_update())
        if contact is None:
            db.rollback()
            raise AppError(404, "contact not found")

        gmail_client = self._client(db)
        collected = collect(
            db,
            contact=contact,
            template_id=template_id,
            settings=self.settings,
            oauth=self.oauth,
            clock=self.clock,
            acknowledge=acknowledge,
            client=gmail_client,
        )
        result = evaluate_gates(collected.gate_input)
        if not result.ok:
            db.rollback()
            raise AppError(422, *(finding.message for finding in result.blockers))

        cap = collected.gate_input.daily_cap
        if counters.reserve_daily_slot(db, day, cap) is None:
            db.rollback()
            raise AppError(
                422, f"Daily cap reached ({cap} for today). Try again tomorrow."
            )

        now = self.clock.now()
        rfc822_id = new_message_id(collected.from_email)
        event = SendEvent(
            contact_id=contact.id,
            template_id=template_id,
            subject_rendered=collected.subject,
            body_rendered=collected.final_body,
            rfc822_message_id=rfc822_id,
            status=SEND_STATUS_QUEUED,
        )
        db.add(event)
        previous_last_sent_at = contact.last_sent_at
        contact.last_sent_at = now
        db.add(contact)
        db.commit()
        db.refresh(event)

        # ------------------------- the side effect ---------------------------
        message = build_outbound_message(
            to_email=contact.email,
            to_name=collected.to_name,
            from_email=collected.from_email,
            sender_name=collected.sender_name,
            reply_to=collected.from_email,
            subject=collected.subject,
            body_plain=collected.final_body,
            body_html=collected.body_html,
            rfc822_message_id=rfc822_id,
            now=now,
        )

        try:
            gmail_message_id = gmail_client.send(encode_raw(message))
        except GmailPermanentError as exc:
            # Gmail rejected it outright, so it was never queued: give the slot
            # back and undo the last_sent_at stamp.
            counters.release_daily_slot(db, day)
            event.status = SEND_STATUS_FAILED
            event.error = str(exc)[:1000]
            event.settled_at = self.clock.now()
            contact.last_sent_at = previous_last_sent_at
            db.add_all([event, contact])
            db.commit()
            raise AppError(502, f"Gmail rejected the message: {exc}") from exc
        except GmailAmbiguousError as exc:
            # It may have gone out. Keep the slot and the last_sent_at stamp; the
            # reconcile CLI resolves the truth later.
            event.status = SEND_STATUS_FAILED
            event.error = f"ambiguous: {exc}"[:1000]
            event.settled_at = self.clock.now()
            db.add(event)
            db.commit()
            raise AppError(
                504,
                "Gmail did not confirm delivery. Check your Sent folder before "
                "retrying, or run the reconcile command.",
            ) from exc

        # ---------------------------- TX2: settle ----------------------------
        settled = self.clock.now()
        event.status = SEND_STATUS_SENT
        event.gmail_message_id = gmail_message_id
        event.sent_at = settled
        event.settled_at = settled
        db.add(event)

        from app.sequences import service as sequences_service

        sequences_service.advance_after_send(
            db,
            contact_id=contact.id,
            template_id=template_id,
            send_event=event,
            clock=self.clock,
        )

        db.commit()
        db.refresh(event)
        return event

    # ------------------------------------------------------------- history ----
    def history(
        self, db: Session, *, contact_id: uuid.UUID | None = None, limit: int = 100
    ) -> list[SendEvent]:
        query = select(SendEvent).order_by(SendEvent.created_at.desc()).limit(limit)
        if contact_id is not None:
            query = query.where(SendEvent.contact_id == contact_id)
        return list(db.scalars(query))

    def last_sent(self, db: Session) -> SendEvent | None:
        return db.scalar(
            select(SendEvent)
            .where(SendEvent.status == SEND_STATUS_SENT)
            .order_by(SendEvent.sent_at.desc())
            .limit(1)
        )

    def stuck_queued(self, db: Session, *, older_than_minutes: int = 5) -> list[SendEvent]:
        """Sends whose outcome we never observed. Surfaced on the dashboard."""
        cutoff = self.clock.now() - dt.timedelta(minutes=older_than_minutes)
        return list(
            db.scalars(
                select(SendEvent)
                .where(SendEvent.status == SEND_STATUS_QUEUED, SendEvent.created_at < cutoff)
                .order_by(SendEvent.created_at)
            )
        )
