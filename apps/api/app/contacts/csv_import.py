"""CSV header mapping and row parsing. Pure — no DB, no network.

Accepts the header spellings that actually turn up in exports: "Work Email",
"First Name", "job_title", "Last", and so on. Only an email column is required.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from app.contacts.constants import HEADER_ALIASES
from app.contacts.normalize import normalize_email, split_full_name

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Fields a CSV may populate directly. full_name is handled separately: it is
# split into first/last only when no dedicated columns are present.
TEXT_FIELDS = ("first_name", "last_name", "company", "title", "hook", "notes", "source")


def normalize_header(header: str) -> str:
    """Fold a header to a lookup key: strip BOM/punctuation, lowercase, underscore."""
    value = (header or "").replace("﻿", "").strip().lower()
    value = _NON_ALNUM.sub("_", value)
    return value.strip("_")


def build_column_map(headers: list[str]) -> dict[str, int]:
    """Map model field -> column index. First matching column for a field wins."""
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        field_name = HEADER_ALIASES.get(normalize_header(header))
        if field_name and field_name not in mapping:
            mapping[field_name] = index
    return mapping


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


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    missing_email: int = 0
    malformed: list[str] = field(default_factory=list)
    truncated: bool = False
    headers_recognised: dict[str, str] = field(default_factory=dict)


class CsvFormatError(ValueError):
    """The upload could not be read as a CSV with an email column."""


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def parse_csv(content: bytes, *, max_rows: int) -> ParseResult:
    """Parse an uploaded CSV into rows, keeping the first occurrence of each email.

    Duplicate detection is case-insensitive and happens here (within the file);
    duplicates against rows already in the database are detected by the service.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError as exc:  # pragma: no cover - latin-1 accepts all bytes
            raise CsvFormatError("File is not valid UTF-8 or Latin-1 text.") from exc

    if not text.strip():
        raise CsvFormatError("The file is empty.")

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise CsvFormatError("The file has no header row.") from exc

    column_map = build_column_map(headers)
    if "email" not in column_map:
        recognised = ", ".join(sorted(column_map)) or "none"
        raise CsvFormatError(
            "No email column found. Add a column named email, Email, or Work Email. "
            f"Columns recognised: {recognised}."
        )

    result = ParseResult(
        headers_recognised={
            headers[index].strip(): field_name for field_name, index in column_map.items()
        }
    )
    seen: set[str] = set()

    for line_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue

        email = normalize_email(_cell(row, column_map.get("email")))
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
        for name in TEXT_FIELDS:
            setattr(parsed, name, _cell(row, column_map.get(name)))

        if not parsed.first_name and not parsed.last_name and "full_name" in column_map:
            parsed.first_name, parsed.last_name = split_full_name(
                _cell(row, column_map["full_name"])
            )

        result.rows.append(parsed)

    return result
