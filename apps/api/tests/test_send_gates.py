"""Send gates. Pure — no database, no network.

GateInput holds only primitives, which is what lets every blocker and warning be
covered here without any I/O.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app.sends.constants import (
    GATE_BODY_EMPTY,
    GATE_CONSUMER_DOMAIN,
    GATE_CONTACT_SUPPRESSED,
    GATE_COOLDOWN_ACTIVE,
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
from app.sends.gates import GateInput, evaluate_gates

NOW = dt.datetime(2026, 3, 2, 4, 0, 0, tzinfo=dt.UTC)  # 14:00 Brisbane

GOOD_BODY = (
    "Hi Avery,\n\nShort note.\n\nJoey\nCEO\nKinnatic Pty Ltd\n"
    'If this isn\'t relevant, reply "no" and I won\'t email again.\n\n'
    "http://localhost:8000/u/token"
)


def gate_input(**overrides) -> GateInput:
    """A GateInput that passes every gate, so each test perturbs exactly one thing."""
    fields = {
        "email": "avery.stone@northwind.example",
        "validation_status": "valid",
        "is_suppressed": False,
        "suppressed_reason": "",
        "company": "Northwind Mutual",
        "title": "CISO",
        "source": "https://example.com/leadership",
        "last_sent_at": None,
        "template_exists": True,
        "subject": "shadow AI + pre-execution control",
        "final_body": GOOD_BODY,
        "leftover_tags": (),
        "gmail_connected": True,
        "from_email": "joey@kinnatic.ai",
        "sender_name": "Joey",
        "company_legal": "Kinnatic Pty Ltd",
        "sends_today": 0,
        "daily_cap": 20,
        "cooldown_days": 14,
        "now": NOW,
        "acknowledge": frozenset(),
    }
    fields.update(overrides)
    return GateInput(**fields)


def codes(findings) -> set[str]:
    return {f.code for f in findings}


# -------------------------------------------------------------- the baseline ----
def test_baseline_is_sendable_with_no_blockers_or_warnings() -> None:
    result = evaluate_gates(gate_input())
    assert result.blockers == ()
    assert result.warnings == ()
    assert result.ok is True


# ------------------------------------------------------------------ blockers ----
def test_gmail_not_connected_blocks() -> None:
    result = evaluate_gates(gate_input(gmail_connected=False))
    assert GATE_GMAIL_NOT_CONNECTED in codes(result.blockers)
    assert result.ok is False


@pytest.mark.parametrize(
    "missing", [{"company_legal": ""}, {"from_email": ""}]
)
def test_incomplete_sender_identity_blocks(missing: dict) -> None:
    result = evaluate_gates(gate_input(**missing))
    assert GATE_SETTINGS_INCOMPLETE in codes(result.blockers)


def test_missing_identity_field_is_named_in_the_message() -> None:
    result = evaluate_gates(gate_input(company_legal=""))
    message = next(f.message for f in result.blockers if f.code == GATE_SETTINGS_INCOMPLETE)
    assert "legal company name" in message


def test_blank_sender_name_alone_does_not_block() -> None:
    """Display name comes from Gmail; stored sender_name is only a fallback."""
    result = evaluate_gates(gate_input(sender_name=""))
    assert GATE_SETTINGS_INCOMPLETE not in codes(result.blockers)


def test_deleted_template_blocks() -> None:
    result = evaluate_gates(gate_input(template_exists=False))
    assert GATE_TEMPLATE_MISSING in codes(result.blockers)


def test_invalid_email_blocks() -> None:
    result = evaluate_gates(gate_input(validation_status="invalid"))
    assert GATE_EMAIL_INVALID in codes(result.blockers)


def test_suppressed_contact_blocks_and_names_the_reason() -> None:
    result = evaluate_gates(gate_input(is_suppressed=True, suppressed_reason="unsub"))
    assert GATE_CONTACT_SUPPRESSED in codes(result.blockers)
    message = next(f.message for f in result.blockers if f.code == GATE_CONTACT_SUPPRESSED)
    assert "unsub" in message


def test_unrendered_merge_tags_block_and_are_listed() -> None:
    result = evaluate_gates(gate_input(leftover_tags=("{{company}}", "{{title}}")))
    assert GATE_UNRENDERED_MERGE_TAGS in codes(result.blockers)
    message = next(f.message for f in result.blockers if f.code == GATE_UNRENDERED_MERGE_TAGS)
    assert "{{company}}" in message and "{{title}}" in message


def test_empty_subject_blocks() -> None:
    assert GATE_SUBJECT_EMPTY in codes(evaluate_gates(gate_input(subject="   ")).blockers)


def test_empty_body_blocks() -> None:
    assert GATE_BODY_EMPTY in codes(evaluate_gates(gate_input(final_body="  ")).blockers)


# ------------------------------------------------------------------ cooldown ----
def test_send_inside_the_cooldown_window_blocks() -> None:
    result = evaluate_gates(gate_input(last_sent_at=NOW - dt.timedelta(days=3)))
    assert GATE_COOLDOWN_ACTIVE in codes(result.blockers)


def test_cooldown_message_names_the_date_it_clears() -> None:
    result = evaluate_gates(gate_input(last_sent_at=NOW - dt.timedelta(days=3)))
    message = next(f.message for f in result.blockers if f.code == GATE_COOLDOWN_ACTIVE)
    assert "2026-03-13" in message, "3 days ago + 14 days"


def test_send_after_the_cooldown_window_is_allowed() -> None:
    result = evaluate_gates(gate_input(last_sent_at=NOW - dt.timedelta(days=15)))
    assert GATE_COOLDOWN_ACTIVE not in codes(result.blockers)


def test_cooldown_boundary_is_inclusive_of_the_clearing_day() -> None:
    """Exactly cooldown_days later is allowed; one day earlier is not."""
    exactly = evaluate_gates(gate_input(last_sent_at=NOW - dt.timedelta(days=14)))
    assert GATE_COOLDOWN_ACTIVE not in codes(exactly.blockers)

    one_short = evaluate_gates(gate_input(last_sent_at=NOW - dt.timedelta(days=13)))
    assert GATE_COOLDOWN_ACTIVE in codes(one_short.blockers)


def test_naive_last_sent_at_is_treated_as_utc_not_an_error() -> None:
    naive = (NOW - dt.timedelta(days=3)).replace(tzinfo=None)
    result = evaluate_gates(gate_input(last_sent_at=naive))
    assert GATE_COOLDOWN_ACTIVE in codes(result.blockers)


# ----------------------------------------------------------------- daily cap ----
def test_daily_cap_reached_blocks() -> None:
    result = evaluate_gates(gate_input(sends_today=20, daily_cap=20))
    assert GATE_DAILY_CAP_REACHED in codes(result.blockers)


def test_one_below_the_cap_is_allowed() -> None:
    result = evaluate_gates(gate_input(sends_today=19, daily_cap=20))
    assert GATE_DAILY_CAP_REACHED not in codes(result.blockers)


def test_cap_lowered_below_current_count_still_blocks() -> None:
    result = evaluate_gates(gate_input(sends_today=20, daily_cap=5))
    assert GATE_DAILY_CAP_REACHED in codes(result.blockers)


# ------------------------------------------------------------------ warnings ----
def test_risky_validation_warns_and_requires_acknowledgement() -> None:
    result = evaluate_gates(gate_input(validation_status="risky"))
    assert GATE_VALIDATION_RISKY in codes(result.warnings)
    assert result.ack_required == (GATE_VALIDATION_RISKY,)
    assert GATE_WARNING_NOT_ACKNOWLEDGED in codes(result.blockers)
    assert result.ok is False, "risky is not sendable until acknowledged"


def test_acknowledging_risky_makes_it_sendable() -> None:
    result = evaluate_gates(
        gate_input(validation_status="risky", acknowledge=frozenset({GATE_VALIDATION_RISKY}))
    )
    assert GATE_VALIDATION_RISKY in codes(result.warnings)
    assert result.blockers == ()
    assert result.ok is True


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("risky", GATE_VALIDATION_RISKY),
        ("pending", GATE_VALIDATION_PENDING),
        ("unknown", GATE_VALIDATION_UNKNOWN),
    ],
)
def test_each_uncertain_validation_status_requires_acknowledgement(
    status: str, code: str
) -> None:
    result = evaluate_gates(gate_input(validation_status=status))
    assert code in codes(result.warnings)
    assert result.ack_required == (code,)


@pytest.mark.parametrize(
    "email",
    [
        "avery@gmail.com",
        "avery@yahoo.com",
        "avery@outlook.com",
        "avery@hotmail.com",
        "avery@icloud.com",
        "avery@bigpond.com",
    ],
)
def test_consumer_domain_warns(email: str) -> None:
    result = evaluate_gates(gate_input(email=email))
    assert GATE_CONSUMER_DOMAIN in codes(result.warnings)


def test_consumer_domain_does_not_block() -> None:
    """It is a judgement call about list quality, not a deliverability failure."""
    result = evaluate_gates(gate_input(email="avery@gmail.com"))
    assert result.ok is True


def test_work_domain_does_not_warn() -> None:
    result = evaluate_gates(gate_input(email="avery@northwind.example"))
    assert GATE_CONSUMER_DOMAIN not in codes(result.warnings)


def test_missing_company_and_title_warn_independently() -> None:
    assert GATE_MISSING_COMPANY in codes(evaluate_gates(gate_input(company="")).warnings)
    assert GATE_MISSING_TITLE in codes(evaluate_gates(gate_input(title="")).warnings)


def test_missing_source_warns_because_it_is_the_evidence_trail() -> None:
    result = evaluate_gates(gate_input(source=""))
    assert GATE_NO_SOURCE_RECORDED in codes(result.warnings)


def test_a_second_link_warns() -> None:
    body = GOOD_BODY + "\n\nhttps://kinnatic.ai/one-pager"
    result = evaluate_gates(gate_input(final_body=body))
    assert GATE_MULTIPLE_LINKS in codes(result.warnings)


def test_the_unsub_link_alone_does_not_warn() -> None:
    result = evaluate_gates(gate_input())
    assert GATE_MULTIPLE_LINKS not in codes(result.warnings)


# ------------------------------------------- acknowledgement cannot clear a blocker ----
def test_acknowledging_everything_cannot_clear_a_real_blocker() -> None:
    """The decisive property: a crafted request cannot talk its way past a gate."""
    every_code = frozenset(
        {
            GATE_GMAIL_NOT_CONNECTED,
            GATE_EMAIL_INVALID,
            GATE_CONTACT_SUPPRESSED,
            GATE_COOLDOWN_ACTIVE,
            GATE_DAILY_CAP_REACHED,
            GATE_UNRENDERED_MERGE_TAGS,
            GATE_VALIDATION_RISKY,
            GATE_WARNING_NOT_ACKNOWLEDGED,
        }
    )
    result = evaluate_gates(
        gate_input(
            is_suppressed=True,
            suppressed_reason="unsub",
            validation_status="invalid",
            sends_today=20,
            leftover_tags=("{{company}}",),
            acknowledge=every_code,
        )
    )
    assert result.ok is False
    assert {
        GATE_EMAIL_INVALID,
        GATE_CONTACT_SUPPRESSED,
        GATE_DAILY_CAP_REACHED,
        GATE_UNRENDERED_MERGE_TAGS,
    } <= codes(result.blockers)


def test_every_blocker_can_fire_at_once() -> None:
    result = evaluate_gates(
        gate_input(
            gmail_connected=False,
            company_legal="",
            from_email="",
            template_exists=False,
            validation_status="invalid",
            is_suppressed=True,
            last_sent_at=NOW - dt.timedelta(days=1),
            sends_today=99,
            leftover_tags=("{{company}}",),
            subject="",
            final_body="",
        )
    )
    assert len(result.blockers) >= 9
    assert result.ok is False
