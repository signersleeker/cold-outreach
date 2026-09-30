"""Start or cancel a template-group sequence for many contacts at once.

Starting is the bulk form of Start sequence: enroll, then send email 1.
Nothing is sent until the operator confirms a preview. Unassign only cancels.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.companies.constants import resolve_industry_filter
from app.contacts import service as contacts_service
from app.contacts.constants import CONTACT_FILTERS
from app.contacts.contact import Contact
from app.contacts.schemas import (
    AssignmentContactDTO,
    GroupAssignmentPreviewDTO,
    GroupAssignmentResultDTO,
)
from app.lib.clock import Clock, local_date
from app.lib.errors import AppError
from app.sends.schemas import GateFindingDTO
from app.sends.services import counters
from app.sends.services.send import SendService
from app.sequences import service as sequences
from app.templates import groups as template_groups
from app.templates.group import TemplateGroup


def _name(contact: Contact) -> str:
    return " ".join(part for part in (contact.first_name, contact.last_name) if part).strip()


def _findings(findings) -> list[GateFindingDTO]:  # noqa: ANN001
    return [
        GateFindingDTO(
            code=finding.code, message=finding.message, requires_ack=finding.requires_ack
        )
        for finding in findings
    ]


def _row(
    contact_id: uuid.UUID,
    *,
    email: str = "",
    name: str = "",
    blockers: list[GateFindingDTO] | None = None,
    warnings: list[GateFindingDTO] | None = None,
) -> AssignmentContactDTO:
    return AssignmentContactDTO(
        contact_id=contact_id,
        email=email,
        name=name,
        blockers=blockers or [],
        warnings=warnings or [],
    )


def _messages(messages: tuple[str, ...]) -> list[GateFindingDTO]:
    return [
        GateFindingDTO(code="send_failed", message=message, requires_ack=False)
        for message in messages
    ]


def resolve_targets(
    db: Session,
    *,
    contact_ids: list[uuid.UUID] | None,
    all_matching: bool,
    q: str,
    status: str,
    industry: str,
    group: str,
) -> list[uuid.UUID]:
    if status not in CONTACT_FILTERS:
        raise AppError(400, f"unknown filter {status!r}")
    if contact_ids:
        seen: set[uuid.UUID] = set()
        ordered: list[uuid.UUID] = []
        for contact_id in contact_ids:
            if contact_id in seen:
                continue
            seen.add(contact_id)
            ordered.append(contact_id)
        return ordered
    if all_matching:
        return contacts_service.matching_ids(
            db,
            q=q,
            status=status,
            industry=resolve_industry_filter(industry),
            group=contacts_service.resolve_group_filter(db, group),
        )
    raise AppError(400, "select at least one contact")


def _require_first_template(
    db: Session, group_id: uuid.UUID
) -> tuple[TemplateGroup, uuid.UUID, str]:
    group = template_groups.require(db, group_id)
    if not group.items:
        raise AppError(400, "that group has no templates")
    first = group.items[0]
    if first.template is None:
        raise AppError(400, "that group's first template no longer exists")
    return group, first.template_id, first.template.name


def preview(
    db: Session,
    send_service: SendService,
    *,
    group_id: uuid.UUID,
    contact_ids: list[uuid.UUID] | None,
    all_matching: bool,
    q: str,
    status: str,
    industry: str,
    group: str,
    acknowledge: frozenset[str],
) -> GroupAssignmentPreviewDTO:
    """Gate email 1 for each contact. Does not enroll and does not send."""
    template_group, template_id, template_name = _require_first_template(db, group_id)
    ids = resolve_targets(
        db,
        contact_ids=contact_ids,
        all_matching=all_matching,
        q=q,
        status=status,
        industry=industry,
        group=group,
    )

    day = local_date(send_service.clock, settings_service.effective_timezone(db))
    simulated = counters.sends_today(db, day)
    daily_cap = settings_service.effective_daily_cap(db)
    sends_today = simulated

    sendable: list[AssignmentContactDTO] = []
    blocked: list[AssignmentContactDTO] = []
    warnings: list[AssignmentContactDTO] = []

    for contact_id in ids:
        contact = contacts_service.get(db, contact_id)
        if contact is None:
            blocked.append(
                _row(
                    contact_id,
                    blockers=[
                        GateFindingDTO(
                            code="contact_missing",
                            message="Contact not found.",
                            requires_ack=False,
                        )
                    ],
                )
            )
            continue

        checked = send_service.preview(
            db,
            contact_id=contact.id,
            template_id=template_id,
            acknowledge=acknowledge,
            assumed_sends_today=simulated,
        )
        row = _row(
            contact.id,
            email=contact.email,
            name=_name(contact),
            blockers=_findings(checked.result.blockers),
            warnings=_findings(checked.result.warnings),
        )
        if checked.result.ok:
            sendable.append(row)
            simulated += 1
            if row.warnings:
                warnings.append(row)
        else:
            blocked.append(row)

    return GroupAssignmentPreviewDTO(
        group_id=template_group.id,
        group_name=template_group.name,
        template_id=template_id,
        template_name=template_name,
        will_send=len(sendable),
        sends_today=sends_today,
        daily_cap=daily_cap,
        sendable=sendable,
        blocked=blocked,
        warnings=warnings,
    )


def apply(
    db: Session,
    send_service: SendService,
    *,
    clock: Clock,
    group_id: uuid.UUID | None,
    contact_ids: list[uuid.UUID] | None,
    all_matching: bool,
    q: str,
    status: str,
    industry: str,
    group: str,
    acknowledge: frozenset[str],
) -> GroupAssignmentResultDTO:
    ids = resolve_targets(
        db,
        contact_ids=contact_ids,
        all_matching=all_matching,
        q=q,
        status=status,
        industry=industry,
        group=group,
    )
    if group_id is None:
        return _unassign(db, ids, clock=clock)

    template_group, template_id, _template_name = _require_first_template(db, group_id)
    sent = 0
    skipped: list[AssignmentContactDTO] = []
    failed: list[AssignmentContactDTO] = []

    for contact_id in ids:
        contact = contacts_service.get(db, contact_id)
        if contact is None:
            skipped.append(
                _row(
                    contact_id,
                    blockers=[
                        GateFindingDTO(
                            code="contact_missing",
                            message="Contact not found.",
                            requires_ack=False,
                        )
                    ],
                )
            )
            continue

        email = contact.email
        name = _name(contact)
        checked = send_service.preview(
            db,
            contact_id=contact.id,
            template_id=template_id,
            acknowledge=acknowledge,
        )
        if not checked.result.ok:
            skipped.append(
                _row(
                    contact.id,
                    email=email,
                    name=name,
                    blockers=_findings(checked.result.blockers),
                    warnings=_findings(checked.result.warnings),
                )
            )
            continue

        try:
            sequences.enroll(
                db,
                contact_id=contact.id,
                group_id=template_group.id,
                clock=clock,
                commit=False,
            )
            send_service.send(
                db,
                contact_id=contact.id,
                template_id=template_id,
                acknowledge=acknowledge,
            )
        except AppError as exc:
            row = _row(
                contact_id,
                email=email,
                name=name,
                blockers=_messages(exc.messages),
            )
            if exc.status_code == 422:
                skipped.append(row)
            else:
                failed.append(row)
            continue

        sent += 1

    return GroupAssignmentResultDTO(sent=sent, unassigned=0, skipped=skipped, failed=failed)


def _unassign(
    db: Session, contact_ids: list[uuid.UUID], *, clock: Clock
) -> GroupAssignmentResultDTO:
    unassigned = 0
    for contact_id in contact_ids:
        enrollment = sequences.cancel_for_contact(db, contact_id, clock=clock, commit=False)
        if enrollment is not None:
            unassigned += 1
    db.commit()
    return GroupAssignmentResultDTO(sent=0, unassigned=unassigned, skipped=[], failed=[])
