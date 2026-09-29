"""Gather everything the gates need. The only I/O in the gate path.

Keeping all reads here means app/sends/gates.py stays pure and every blocker and
warning is unit-testable without a database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.config import Settings
from app.contacts.contact import Contact
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock, brisbane_date
from app.sends.gates import GateInput
from app.sends.services import counters
from app.sends.services.compose import compose_final_body
from app.suppressions import service as suppressions_service
from app.templates import service as templates_service
from app.templates.render import build_context, render


@dataclass(frozen=True)
class CollectedSend:
    """Gate inputs plus the rendered artefacts the send path needs."""

    gate_input: GateInput
    subject: str
    final_body: str
    unsub_url: str
    from_email: str
    sender_name: str
    to_name: str
    previous_last_sent_at: object


def collect(
    db: Session,
    *,
    contact: Contact,
    template_id: uuid.UUID,
    settings: Settings,
    oauth: GmailOAuthService,
    clock: Clock,
    acknowledge: frozenset[str],
) -> CollectedSend:
    app_settings = settings_service.get_or_create(db)
    template = templates_service.get(db, template_id)
    day = brisbane_date(clock)

    context = build_context(
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        title=contact.title,
        hook=contact.hook,
        sender_name=app_settings.sender_name,
        sender_title=app_settings.sender_title,
        company_legal=app_settings.company_legal,
    )

    if template is None:
        rendered_subject, rendered_body, leftover = "", "", ()
    else:
        result = render(template.subject, template.body, context)
        rendered_subject, rendered_body = result.subject, result.body
        leftover = result.leftover_tags

    unsub_url = settings.unsub_url(contact.unsub_token)
    final_body = (
        compose_final_body(
            rendered_body,
            sender_name=app_settings.sender_name,
            sender_title=app_settings.sender_title,
            company_legal=app_settings.company_legal,
            unsub_url=unsub_url,
        )
        if template is not None
        else ""
    )

    # Authoritative suppression check — the suppressions table, not the cached
    # boolean on the contact row.
    suppression = suppressions_service.is_suppressed(db, contact.email)

    gate_input = GateInput(
        email=contact.email,
        validation_status=contact.validation_status,
        is_suppressed=suppression is not None,
        suppressed_reason=suppression.reason if suppression else "",
        company=contact.company,
        title=contact.title,
        source=contact.source,
        last_sent_at=contact.last_sent_at,
        template_exists=template is not None,
        subject=rendered_subject,
        final_body=final_body,
        leftover_tags=leftover,
        gmail_connected=oauth.is_connected(db),
        from_email=app_settings.from_email,
        sender_name=app_settings.sender_name,
        company_legal=app_settings.company_legal,
        sends_today=counters.sends_today(db, day),
        daily_cap=settings_service.effective_daily_cap(db),
        cooldown_days=settings.cooldown_days,
        now=clock.now(),
        acknowledge=acknowledge,
    )

    return CollectedSend(
        gate_input=gate_input,
        subject=rendered_subject,
        final_body=final_body,
        unsub_url=unsub_url,
        from_email=app_settings.from_email,
        sender_name=app_settings.sender_name,
        to_name=" ".join(p for p in (contact.first_name, contact.last_name) if p).strip(),
        previous_last_sent_at=contact.last_sent_at,
    )
