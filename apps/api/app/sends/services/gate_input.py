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
from app.gmail.client import GmailClient
from app.gmail.constants import GMAIL_SETTINGS_SCOPE
from app.gmail.exceptions import GmailPermanentError
from app.gmail.mime import build_message_parts
from app.gmail.oauth_service import GmailOAuthService
from app.lib.clock import Clock, local_date
from app.sends.gates import GateInput
from app.sends.services import counters
from app.sends.services.compose import compose_gate_body
from app.suppressions import service as suppressions_service
from app.templates import service as templates_service
from app.templates.render import build_context, render


@dataclass(frozen=True)
class CollectedSend:
    """Gate inputs plus the rendered artefacts the send path needs."""

    gate_input: GateInput
    subject: str
    final_body: str
    body_html: str
    signature_html: str
    unsub_url: str
    from_email: str
    sender_name: str
    to_name: str
    previous_last_sent_at: object


def _load_send_as(
    db: Session,
    *,
    oauth: GmailOAuthService,
    from_email: str,
    client: GmailClient | None = None,
) -> tuple[str, str]:
    """Return (display_name, signature_html) from Gmail when the scope is granted."""
    row = oauth.current(db)
    if row is None or not oauth.is_connected(db):
        return "", ""
    scopes = row.scopes.split() if row.scopes else []
    if GMAIL_SETTINGS_SCOPE not in scopes:
        return "", ""
    email = from_email or row.email
    if not email:
        return "", ""
    try:
        gmail = client if client is not None else oauth.client(db)
        send_as = gmail.get_send_as(email)
    except GmailPermanentError:
        return "", ""
    except Exception:
        return "", ""
    return send_as.display_name.strip(), send_as.signature


def collect(
    db: Session,
    *,
    contact: Contact,
    template_id: uuid.UUID,
    settings: Settings,
    oauth: GmailOAuthService,
    clock: Clock,
    acknowledge: frozenset[str],
    client: GmailClient | None = None,
) -> CollectedSend:
    app_settings = settings_service.get_or_create(db)
    template = templates_service.get(db, template_id)
    day = local_date(clock, settings_service.effective_timezone(db))

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

    unsub_url = (
        settings.unsub_url(contact.unsub_token) if app_settings.include_unsub_link else ""
    )
    display_name, signature_html = _load_send_as(
        db, oauth=oauth, from_email=app_settings.from_email, client=client
    )
    sender_name = display_name or app_settings.sender_name

    # Gate body excludes the signature so signature links never trip
    # the multiple_links warning.
    gate_body = (
        compose_gate_body(rendered_body, unsub_url=unsub_url) if template is not None else ""
    )
    if template is not None:
        final_body, body_html = build_message_parts(
            rendered_body=rendered_body,
            signature_html=signature_html,
            unsub_url=unsub_url,
        )
    else:
        final_body, body_html = "", ""

    # Authoritative suppression check — the suppressions table, not the cached
    # boolean on the contact row.
    suppression = suppressions_service.is_suppressed(db, contact.email)

    from app.sequences import service as sequences_service

    skip_cooldown = sequences_service.is_current_due_template(
        db,
        contact_id=contact.id,
        template_id=template_id,
        today=day,
    )

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
        final_body=gate_body,
        leftover_tags=leftover,
        gmail_connected=oauth.is_connected(db),
        from_email=app_settings.from_email,
        sender_name=sender_name,
        company_legal=app_settings.company_legal,
        sends_today=counters.sends_today(db, day),
        daily_cap=settings_service.effective_daily_cap(db),
        cooldown_days=settings.cooldown_days,
        now=clock.now(),
        acknowledge=acknowledge,
        skip_cooldown=skip_cooldown,
    )

    return CollectedSend(
        gate_input=gate_input,
        subject=rendered_subject,
        final_body=final_body,
        body_html=body_html,
        signature_html=signature_html,
        unsub_url=unsub_url,
        from_email=app_settings.from_email,
        sender_name=sender_name,
        to_name=" ".join(p for p in (contact.first_name, contact.last_name) if p).strip(),
        previous_last_sent_at=contact.last_sent_at,
    )
