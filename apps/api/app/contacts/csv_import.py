"""CSV header mapping and row parsing. Pure — no DB, no network.

Headers can be auto-suggested from common aliases, then confirmed by the
operator before import. Only an email column is required.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field

from app.contacts.constants import HEADER_ALIASES
from app.contacts.normalize import normalize_email, split_full_name

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Fields a CSV may populate directly. full_name is handled separately: it is
# split into first/last only when no dedicated columns are present.
TEXT_FIELDS = ("first_name", "last_name", "company", "title", "hook", "notes", "source")
# Stored on the company row, not the contact.
COMPANY_FIELDS = ("website", "industry", "location")
# Become rows in the polymorphic notes table.
NOTE_FIELDS = ("contact_notes", "company_notes")
IMPORTABLE_FIELDS = frozenset({"email", "full_name", *TEXT_FIELDS, *COMPANY_FIELDS, *NOTE_FIELDS})


def normalize_header(header: str) -> str:
    """Fold a header to a lookup key: strip BOM/punctuation, lowercase, underscore."""
    value = (header or "").replace("﻿", "").strip().lower()
    value = _NON_ALNUM.sub("_", value)
    return value.strip("_")


def build_column_map(headers: list[str]) -> dict[str, int]:
    """Map model field -> column index via aliases. First matching column for a field wins."""
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        field_name = HEADER_ALIASES.get(normalize_header(header))
        if field_name and field_name not in mapping:
            mapping[field_name] = index
    return mapping


def suggest_field(header: str) -> str | None:
    """Suggested import field for a header, or None to ignore."""
    return HEADER_ALIASES.get(normalize_header(header))


def column_map_from_mapping(headers: list[str], mapping: dict[str, str]) -> dict[str, int]:
    """Build field -> index from an explicit header -> field mapping.

    ``mapping`` keys are the raw header strings from the file (stripped). Values
    are importable field names, or empty / "ignore" to skip the column.
    """
    by_header = {h.strip(): field_name for h, field_name in mapping.items()}
    result: dict[str, int] = {}
    for index, header in enumerate(headers):
        field_name = (by_header.get(header.strip()) or "").strip()
        if not field_name or field_name == "ignore":
            continue
        if field_name not in IMPORTABLE_FIELDS:
            raise CsvFormatError(
                f"Unknown field {field_name!r} for column {header.strip()!r}. "
                f"Allowed: {', '.join(sorted(IMPORTABLE_FIELDS))}."
            )
        if field_name in result:
            raise CsvFormatError(
                f"Field {field_name!r} is mapped to more than one column. "
                "Assign each field to exactly one column."
            )
        result[field_name] = index
    return result


@dataclass
class ParsedRow:
    line_number: int
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: str = ""
    hook: str = ""
    notes: str = ""
    source: str = ""
    website: str = ""
    industry: str = ""
    location: str = ""
    contact_notes: str = ""
    company_notes: str = ""


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    missing_email: int = 0
    malformed: list[str] = field(default_factory=list)
    truncated: bool = False
    headers_recognised: dict[str, str] = field(default_factory=dict)


@dataclass
class PreviewResult:
    headers: list[str]
    suggestions: dict[str, str | None]


class CsvFormatError(ValueError):
    """The upload could not be read as a CSV with an email column."""


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError as exc:  # pragma: no cover - latin-1 accepts all bytes
            raise CsvFormatError("File is not valid UTF-8 or Latin-1 text.") from exc


def _read_headers(content: bytes) -> tuple[list[str], csv.reader]:
    text = _decode(content)
    if not text.strip():
        raise CsvFormatError("The file is empty.")
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise CsvFormatError("The file has no header row.") from exc
    return headers, reader


def preview_csv(content: bytes) -> PreviewResult:
    """Return header names and a suggested field for each (or None to ignore)."""
    headers, _ = _read_headers(content)
    cleaned = [h.strip() for h in headers]
    if not any(cleaned):
        raise CsvFormatError("The file has no header row.")
    return PreviewResult(
        headers=cleaned,
        suggestions={h: suggest_field(h) for h in cleaned},
    )


def parse_mapping_json(raw: str | None) -> dict[str, str] | None:
    """Parse the mapping form field. Empty / missing means use auto aliases."""
    if raw is None or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CsvFormatError("column mapping must be valid JSON") from exc
    if not isinstance(data, dict):
        raise CsvFormatError("column mapping must be a JSON object of header → field")
    return {str(k): str(v) for k, v in data.items()}


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def parse_csv(
    content: bytes,
    *,
    max_rows: int,
    column_map: dict[str, str] | None = None,
) -> ParseResult:
    """Parse an uploaded CSV into rows, keeping the first occurrence of each email.

    Duplicate detection is case-insensitive and happens here (within the file);
    duplicates against rows already in the database are detected by the service.

    When ``column_map`` is provided it is header text → field name from the
    operator. Otherwise aliases are applied automatically.
    """
    headers, reader = _read_headers(content)

    if column_map is not None:
        field_to_index = column_map_from_mapping(headers, column_map)
    else:
        field_to_index = build_column_map(headers)

    if "email" not in field_to_index:
        recognised = ", ".join(sorted(field_to_index)) or "none"
        raise CsvFormatError(
            "No email column found. Map a column to email. "
            f"Columns recognised: {recognised}."
        )

    result = ParseResult(
        headers_recognised={
            headers[index].strip(): field_name for field_name, index in field_to_index.items()
        }
    )
    seen: set[str] = set()

    for line_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue

        email = normalize_email(_cell(row, field_to_index.get("email")))
        if not email:
            result.missing_email += 1
            continue
        if email in seen:
            continue
        seen.add(email)

        if len(result.rows) >= max_rows:
            result.truncated = True
            break

        parsed = ParsedRow(line_number=line_number, email=email)
        for name in (*TEXT_FIELDS, *COMPANY_FIELDS, *NOTE_FIELDS):
            setattr(parsed, name, _cell(row, field_to_index.get(name)))

        if not parsed.first_name and not parsed.last_name and "full_name" in field_to_index:
            parsed.first_name, parsed.last_name = split_full_name(
                _cell(row, field_to_index["full_name"])
            )

        result.rows.append(parsed)

    return result
