"""Mustache-style {{tag}} substitution. Pure — no DB, no I/O.

A mustache library would bring sections, partials, lambdas and HTML escaping,
every one of which is useless or actively harmful in a plain-text cold email.
What we need is one rule with a precise behaviour for *absent* values, because
that behaviour is the whole compliance story:

    An absent value leaves the literal {{tag}} in place, and a leftover tag is
    a hard send blocker.

So "missing required merge fields that would leave {{...}} in the output" is
literally true rather than needing a second parallel check, and a typo'd
{{industy}} fails closed instead of emailing a CISO a raw template tag.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.templates.constants import KNOWN_VARS

TAG_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

# Deliberately looser than TAG_RE: it also catches malformed leftovers such as
# {{ first name }} or {{}} that TAG_RE would not treat as a tag at all.
LEFTOVER_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)


@dataclass(frozen=True)
class RenderResult:
    subject: str
    body: str
    used_vars: frozenset[str]
    unknown_vars: tuple[str, ...]
    missing_vars: tuple[str, ...]

    @property
    def leftover_tags(self) -> tuple[str, ...]:
        found = LEFTOVER_RE.findall(self.subject) + LEFTOVER_RE.findall(self.body)
        return tuple(dict.fromkeys(found))


def referenced_vars(*texts: str) -> tuple[str, ...]:
    """Every tag name a template mentions, in first-seen order."""
    names: list[str] = []
    for text in texts:
        names.extend(TAG_RE.findall(text))
    return tuple(dict.fromkeys(names))


def unknown_vars(*texts: str) -> tuple[str, ...]:
    return tuple(name for name in referenced_vars(*texts) if name not in KNOWN_VARS)


def sanitize_value(value: object) -> str:
    """Stringify a merge value and strip brace pairs out of it.

    Contact data is data, not template source. Without this a hook containing
    "{{x}}" would trip the leftover scan and block an otherwise fine send.
    """
    if value is None:
        return ""
    return str(value).replace("{{", "").replace("}}", "").strip()


def render_text(text: str, ctx: Mapping[str, str]) -> tuple[str, set[str], set[str]]:
    """Substitute tags in one string.

    Returns (output, substituted_names, missing_names). A tag whose value is
    absent or empty is left in place verbatim.

    Single pass: re.sub never rescans its own replacements, so a value that
    happens to contain a tag cannot expand.
    """
    substituted: set[str] = set()
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = ctx.get(name, "")
        if not value:
            missing.add(name)
            return match.group(0)
        substituted.add(name)
        return value

    return TAG_RE.sub(replace, text), substituted, missing


def render(subject: str, body: str, ctx: Mapping[str, str]) -> RenderResult:
    rendered_subject, used_s, missing_s = render_text(subject, ctx)
    rendered_body, used_b, missing_b = render_text(body, ctx)
    return RenderResult(
        subject=rendered_subject,
        body=rendered_body,
        used_vars=frozenset(used_s | used_b),
        unknown_vars=unknown_vars(subject, body),
        missing_vars=tuple(sorted(missing_s | missing_b)),
    )


def build_context(
    *,
    first_name: str = "",
    last_name: str = "",
    company: str = "",
    title: str = "",
    hook: str = "",
    sender_name: str = "",
    sender_title: str = "",
    company_legal: str = "",
) -> dict[str, str]:
    """Sanitised merge context. Keys match KNOWN_VARS exactly."""
    return {
        "first_name": sanitize_value(first_name),
        "last_name": sanitize_value(last_name),
        "company": sanitize_value(company),
        "title": sanitize_value(title),
        "hook": sanitize_value(hook),
        "sender_name": sanitize_value(sender_name),
        "sender_title": sanitize_value(sender_title),
        "company_legal": sanitize_value(company_legal),
    }
