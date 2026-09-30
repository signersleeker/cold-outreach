"""Send gates. Pure — no Session, no httpx, no ORM.

One function, two callers: POST /sends/preview shows the operator what would
happen, and POST /sends re-runs the identical function inside the reserving
transaction. The UI is never trusted; the disabled Send button is a courtesy and
this function is the control.

GateInput deliberately holds only primitives. That is what makes
tests/sends/test_gates.py a pure unit test covering every blocker and warning
without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contacts.constants import (
    CONSUMER_DOMAINS,
    VALIDATION_INVALID,
    VALIDATION_PENDING,
    VALIDATION_RISKY,
    VALIDATION_UNKNOWN,
)
from app.lib.text import count_http_links
from app.sends.constants import (
    GATE_BODY_EMPTY,
    GATE_CONSUMER_DOMAIN,
    GATE_CONTACT_SUPPRESSED,
    GATE_DAILY_CAP_REACHED,
    GATE_EMAIL_INVALID,
    GATE_GMAIL_NOT_CONNECTED,
    GATE_MISSING_COMPANY,
    GATE_MISSING_TITLE,
    GATE_MULTIPLE_LINKS,
    GATE_NO_SOURCE_RECORDED,
    GATE_SETTINGS_INCOMPLETE,
    GATE_SUBJECT_EMPTY,
    GATE_TEMPLATE_MISSING,
    GATE_UNRENDERED_MERGE_TAGS,
    GATE_VALIDATION_PENDING,
    GATE_VALIDATION_RISKY,
    GATE_VALIDATION_UNKNOWN,
    GATE_WARNING_NOT_ACKNOWLEDGED,
)


@dataclass(frozen=True)
class GateFinding:
    code: str
    message: str
    requires_ack: bool = False


@dataclass(frozen=True)
class GateResult:
    blockers: tuple[GateFinding, ...]
    warnings: tuple[GateFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def ack_required(self) -> tuple[str, ...]:
        return tuple(w.code for w in self.warnings if w.requires_ack)


@dataclass(frozen=True)
class GateInput:
    # --- contact ---
    email: str
    validation_status: str
    is_suppressed: bool
    suppressed_reason: str
    company: str
    title: str
    source: str
    # --- template / rendered output ---
    template_exists: bool
    subject: str
    final_body: str
    leftover_tags: tuple[str, ...]
    # --- environment ---
    gmail_connected: bool
    from_email: str
    sender_name: str
    company_legal: str
    sends_today: int
    daily_cap: int
    acknowledge: frozenset[str] = field(default_factory=frozenset)


def _domain_of(email: str) -> str:
    _, _, domain = email.rpartition("@")
    return domain.lower()


def evaluate_gates(i: GateInput) -> GateResult:
    blockers: list[GateFinding] = []
    warnings: list[GateFinding] = []

    # ---------------------------------------------------------- blockers ----
    if not i.gmail_connected:
        blockers.append(
            GateFinding(
                GATE_GMAIL_NOT_CONNECTED,
                "No Gmail mailbox is connected. Connect one in Settings.",
            )
        )

    missing_identity = [
        label
        for label, value in (
            ("legal company name", i.company_legal),
            ("from address", i.from_email),
        )
        if not value.strip()
    ]
    if missing_identity:
        blockers.append(
            GateFinding(
                GATE_SETTINGS_INCOMPLETE,
                f"Sender settings incomplete: missing {', '.join(missing_identity)}.",
            )
        )

    if not i.template_exists:
        blockers.append(GateFinding(GATE_TEMPLATE_MISSING, "That template no longer exists."))

    if i.validation_status == VALIDATION_INVALID:
        blockers.append(
            GateFinding(GATE_EMAIL_INVALID, f"{i.email} failed email validation.")
        )

    if i.is_suppressed:
        reason = i.suppressed_reason or "suppressed"
        blockers.append(
            GateFinding(
                GATE_CONTACT_SUPPRESSED,
                f"{i.email} is on the suppression list ({reason}).",
            )
        )

    if i.sends_today >= i.daily_cap:
        blockers.append(
            GateFinding(
                GATE_DAILY_CAP_REACHED,
                    f"Daily cap reached ({i.sends_today}/{i.daily_cap} for today).",
            )
        )

    if i.leftover_tags:
        blockers.append(
            GateFinding(
                GATE_UNRENDERED_MERGE_TAGS,
                "Unfilled merge fields would go out as-is: "
                f"{', '.join(i.leftover_tags)}. Fill them on the contact or pick "
                "another template.",
            )
        )

    if not i.subject.strip():
        blockers.append(GateFinding(GATE_SUBJECT_EMPTY, "Subject is empty."))

    if not i.final_body.strip():
        blockers.append(GateFinding(GATE_BODY_EMPTY, "Body is empty."))

    # ---------------------------------------------------------- warnings ----
    if i.validation_status == VALIDATION_RISKY:
        warnings.append(
            GateFinding(
                GATE_VALIDATION_RISKY,
                "Validation came back risky (usually a catch-all domain) — "
                "delivery is not guaranteed.",
                requires_ack=True,
            )
        )
    elif i.validation_status == VALIDATION_PENDING:
        warnings.append(
            GateFinding(
                GATE_VALIDATION_PENDING,
                "This address has not been validated yet.",
                requires_ack=True,
            )
        )
    elif i.validation_status == VALIDATION_UNKNOWN:
        warnings.append(
            GateFinding(
                GATE_VALIDATION_UNKNOWN,
                "Validation could not reach a verdict for this address.",
                requires_ack=True,
            )
        )

    if _domain_of(i.email) in CONSUMER_DOMAINS:
        warnings.append(
            GateFinding(
                GATE_CONSUMER_DOMAIN,
                f"{_domain_of(i.email)} is a personal mailbox provider, not a work domain.",
            )
        )

    if not i.company.strip():
        warnings.append(GateFinding(GATE_MISSING_COMPANY, "No company recorded."))
    if not i.title.strip():
        warnings.append(GateFinding(GATE_MISSING_TITLE, "No job title recorded."))

    link_count = count_http_links(i.final_body)
    if link_count > 1:
        warnings.append(
            GateFinding(
                GATE_MULTIPLE_LINKS,
                f"Body contains {link_count} links including the unsubscribe URL. "
                "More than one reads as marketing.",
            )
        )

    if not i.source.strip():
        warnings.append(
            GateFinding(
                GATE_NO_SOURCE_RECORDED,
                "No source recorded for this address. That is your evidence for "
                "why contacting this person is defensible.",
            )
        )

    # An unacknowledged warning that requires acknowledgement becomes a blocker.
    # This is what makes the "send anyway" checkbox a server-side rule rather
    # than something a curl request can skip.
    unacknowledged = [w.code for w in warnings if w.requires_ack and w.code not in i.acknowledge]
    if unacknowledged:
        blockers.append(
            GateFinding(
                GATE_WARNING_NOT_ACKNOWLEDGED,
                "Confirm you want to send anyway: " + ", ".join(unacknowledged),
            )
        )

    return GateResult(blockers=tuple(blockers), warnings=tuple(warnings))
