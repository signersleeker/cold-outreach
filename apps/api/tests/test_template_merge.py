"""Template merge and body composition. Pure — no database.

The load-bearing rule: an absent value leaves the literal {{tag}} in place, which
is what turns "missing merge field" into a detectable hard blocker.
"""

from __future__ import annotations

import pytest

from app.lib.text import count_http_links
from app.sends.services.compose import (
    append_unsub_line,
    build_identity_block,
    compose_final_body,
    ensure_identity_block,
    has_identity_block,
)
from app.templates.constants import (
    FIRST_TOUCH_BODY,
    FIRST_TOUCH_SUBJECT,
    FOLLOW_UP_BODY,
    OPT_OUT_SENTENCE,
)
from app.templates.render import (
    build_context,
    referenced_vars,
    render,
    sanitize_value,
    unknown_vars,
)

IDENTITY = {
    "sender_name": "Joey",
    "sender_title": "CEO",
    "company_legal": "Kinnatic Pty Ltd",
}


def full_context(**overrides) -> dict[str, str]:
    """Build a context through build_context, so values go through sanitisation."""
    fields = {
        "first_name": "Avery",
        "last_name": "Stone",
        "company": "Northwind Mutual",
        "title": "CISO",
        "hook": "CPS 234 uplift",
        **IDENTITY,
    }
    fields.update(overrides)
    return build_context(**fields)


# ------------------------------------------------------------- substitution ----
def test_all_tags_substituted() -> None:
    result = render("Hi {{first_name}}", "{{company}} / {{title}} / {{hook}}", full_context())
    assert result.subject == "Hi Avery"
    assert result.body == "Northwind Mutual / CISO / CPS 234 uplift"
    assert result.leftover_tags == ()


def test_whitespace_inside_tags_is_tolerated() -> None:
    result = render("{{ first_name }}", "{{  company  }}", full_context())
    assert result.subject == "Avery"
    assert result.body == "Northwind Mutual"


def test_repeated_tag_is_substituted_everywhere() -> None:
    result = render("x", "{{first_name}} {{first_name}}", full_context())
    assert result.body == "Avery Avery"


# ------------------------------------------------- absent values leave the tag ----
def test_empty_value_leaves_the_tag_in_place() -> None:
    result = render("x", "Hi {{first_name}}, at {{company}}", full_context(company=""))
    assert result.body == "Hi Avery, at {{company}}"
    assert result.leftover_tags == ("{{company}}",)
    assert "company" in result.missing_vars


def test_unknown_tag_is_left_in_place_and_reported() -> None:
    result = render("x", "Your {{industry}} peers", full_context())
    assert result.body == "Your {{industry}} peers"
    assert result.leftover_tags == ("{{industry}}",)
    assert unknown_vars("x", "Your {{industry}} peers") == ("industry",)


def test_leftover_detection_catches_malformed_tags() -> None:
    """{{ first name }} is not a valid tag, so it must still be caught."""
    result = render("x", "Hi {{ first name }}", full_context())
    assert result.leftover_tags == ("{{ first name }}",)


def test_multiple_leftovers_are_deduplicated() -> None:
    result = render("{{company}}", "{{company}} and {{title}}", full_context(company="", title=""))
    assert set(result.leftover_tags) == {"{{company}}", "{{title}}"}
    assert len(result.leftover_tags) == 2


def test_leftover_in_subject_alone_is_detected() -> None:
    result = render("Shadow AI at {{company}}", "body", full_context(company=""))
    assert result.leftover_tags == ("{{company}}",)


# ------------------------------------------------------------ value hygiene ----
def test_braces_in_contact_data_do_not_cause_a_false_block() -> None:
    """build_context strips brace pairs, so a hook containing them is still sendable.

    Without this a prospect whose hook mentioned "{{x}}" would trip the leftover
    scan and be permanently unsendable.
    """
    result = render("x", "{{hook}}", full_context(hook="see {{company}}"))
    assert result.body == "see company"
    assert result.leftover_tags == ()


def test_a_raw_value_still_cannot_expand_into_a_substitution() -> None:
    """Belt and braces: even unsanitised, one re.sub pass never rescans output.

    So the worst case is a literal leftover tag, which fails closed at the gate
    rather than silently merging the wrong field.
    """
    ctx = full_context()
    ctx["hook"] = "see {{company}}"  # deliberately bypassing build_context
    result = render("x", "{{hook}}", ctx)
    assert result.body == "see {{company}}"
    assert result.leftover_tags == ("{{company}}",), "fails closed as a blocker"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  padded  ", "padded"),
        ("{{nested}}", "nested"),
        (None, ""),
        (42, "42"),
    ],
)
def test_sanitize_value(raw: object, expected: str) -> None:
    assert sanitize_value(raw) == expected


def test_referenced_vars_preserves_first_seen_order() -> None:
    assert referenced_vars("{{b}}", "{{a}} {{b}} {{c}}") == ("b", "a", "c")


# ----------------------------------------------- the seeded default template ----
def test_first_touch_template_renders_with_no_leftovers() -> None:
    result = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context())
    assert result.leftover_tags == ()
    assert "Avery" in result.body
    assert "Northwind Mutual" in result.body
    assert "CISO" in result.body


def test_first_touch_subject_has_no_merge_tags() -> None:
    """A tag in the subject would block every contact missing that field."""
    assert referenced_vars(FIRST_TOUCH_SUBJECT) == ()


def test_first_touch_blocks_when_company_is_missing() -> None:
    result = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context(company=""))
    assert result.leftover_tags == ("{{company}}",)


def test_both_seeded_templates_carry_the_opt_out_sentence() -> None:
    for body in (FIRST_TOUCH_BODY, FOLLOW_UP_BODY):
        assert OPT_OUT_SENTENCE in body


def test_seeded_templates_contain_no_unsubscribe_footer_language() -> None:
    for body in (FIRST_TOUCH_BODY, FOLLOW_UP_BODY):
        lowered = body.lower()
        assert "click here" not in lowered
        assert "unsubscribe" not in lowered, "an opt-out sentence, not a marketing footer"
        assert "http" not in lowered


# --------------------------------------------------------- identity block ----
def test_build_identity_block_shape() -> None:
    assert build_identity_block("Joey", "CEO", "Kinnatic Pty Ltd") == (
        f"Joey\nCEO\nKinnatic Pty Ltd\n{OPT_OUT_SENTENCE}"
    )


def test_identity_block_appended_to_a_bare_body() -> None:
    out = ensure_identity_block("Hi Avery,\n\nShort note.", **IDENTITY)
    assert out.endswith(OPT_OUT_SENTENCE)
    assert "Kinnatic Pty Ltd" in out


def test_identity_block_is_not_duplicated_on_the_seeded_body() -> None:
    """The seeded first-touch body already ends with the block."""
    rendered = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context()).body
    assert has_identity_block(rendered, "Kinnatic Pty Ltd") is True
    assert ensure_identity_block(rendered, **IDENTITY) == rendered
    assert rendered.count(OPT_OUT_SENTENCE) == 1


def test_ensure_identity_block_is_idempotent() -> None:
    once = ensure_identity_block("Hi Avery,", **IDENTITY)
    assert ensure_identity_block(once, **IDENTITY) == once
    assert once.count(OPT_OUT_SENTENCE) == 1


def test_identity_block_detected_through_curly_apostrophes() -> None:
    """A template edited in a word processor gets typographic quotes."""
    curly = "Hi Avery,\n\nJoey\nCEO\nKinnatic Pty Ltd\nIf this isn’t relevant, reply “no” and I won’t email again."
    assert has_identity_block(curly, "Kinnatic Pty Ltd") is True
    assert ensure_identity_block(curly, **IDENTITY) == curly


def test_opt_out_without_the_company_is_not_a_complete_block() -> None:
    body = f"Hi Avery,\n\n{OPT_OUT_SENTENCE}"
    assert has_identity_block(body, "Kinnatic Pty Ltd") is False


# ------------------------------------------------------------- unsub line ----
def test_unsub_line_is_on_its_own_line() -> None:
    out = append_unsub_line("Body text.", "http://localhost:8000/u/abc123")
    assert out.splitlines()[-1] == "http://localhost:8000/u/abc123"


def test_unsub_line_is_idempotent() -> None:
    url = "http://localhost:8000/u/abc123"
    once = append_unsub_line("Body.", url)
    assert append_unsub_line(once, url) == once
    assert once.count(url) == 1


# ------------------------------------------------------ full composition ----
def test_compose_final_body_appends_each_part_exactly_once() -> None:
    rendered = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context()).body
    url = "http://localhost:8000/u/tok"
    final = compose_final_body(rendered, unsub_url=url, **IDENTITY)

    assert final.count(OPT_OUT_SENTENCE) == 1
    assert final.count("Kinnatic Pty Ltd") == 1
    assert final.count(url) == 1
    assert final.splitlines()[-1] == url


def test_compose_final_body_is_idempotent() -> None:
    rendered = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context()).body
    url = "http://localhost:8000/u/tok"
    once = compose_final_body(rendered, unsub_url=url, **IDENTITY)
    assert compose_final_body(once, unsub_url=url, **IDENTITY) == once


def test_composed_body_has_exactly_one_link() -> None:
    rendered = render(FIRST_TOUCH_SUBJECT, FIRST_TOUCH_BODY, full_context()).body
    final = compose_final_body(rendered, unsub_url="http://localhost:8000/u/tok", **IDENTITY)
    assert count_http_links(final) == 1, "only the unsubscribe URL"


# --------------------------------------------------------------- link count ----
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no links here", 0),
        ("one http://a.example/x", 1),
        ("http://a.example and https://b.example/y", 2),
        ("trailing punctuation https://a.example/x.", 1),
        ("in parens (https://a.example/x)", 1),
    ],
)
def test_count_http_links(text: str, expected: int) -> None:
    assert count_http_links(text) == expected
