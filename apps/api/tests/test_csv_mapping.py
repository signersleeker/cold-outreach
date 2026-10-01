"""CSV header mapping and row parsing. Pure — no database."""

from __future__ import annotations

import pytest

from app.contacts.csv_import import (
    CsvFormatError,
    build_column_map,
    normalize_header,
    parse_csv,
    preview_csv,
)
from app.contacts.normalize import normalize_email, split_full_name

MAX_ROWS = 500


def parse(text: str, max_rows: int = MAX_ROWS):
    return parse_csv(text.encode("utf-8"), max_rows=max_rows)


# ------------------------------------------------------------ header folding ----
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Work Email", "work_email"),
        ("  First Name  ", "first_name"),
        ("job_title", "job_title"),
        ("Job-Title", "job_title"),
        ("E-Mail", "e_mail"),
        ("Company  Name", "company_name"),
        ("﻿Email", "email"),
        ("Source URL", "source_url"),
    ],
)
def test_normalize_header(raw: str, expected: str) -> None:
    assert normalize_header(raw) == expected


def test_build_column_map_resolves_aliases() -> None:
    headers = ["Work Email", "First Name", "Last", "Company", "Job Title", "hook", "Notes", "Source"]
    assert build_column_map(headers) == {
        "email": 0,
        "first_name": 1,
        "last_name": 2,
        "company": 3,
        "title": 4,
        "hook": 5,
        "source": 7,
    }


def test_build_column_map_first_match_wins() -> None:
    """Two columns both mapping to email: the first is used, not the last."""
    assert build_column_map(["Email", "Work Email"])["email"] == 0


def test_build_column_map_ignores_unknown_columns() -> None:
    mapping = build_column_map(["Email", "Lead Score", "Random Column"])
    assert mapping == {"email": 0}


# --------------------------------------------------------------- email column ----
def test_email_column_is_required() -> None:
    with pytest.raises(CsvFormatError, match="No email column"):
        parse("First Name,Company\nAvery,Northwind\n")


def test_error_names_the_columns_it_did_recognise() -> None:
    with pytest.raises(CsvFormatError, match="company"):
        parse("First Name,Company\nAvery,Northwind\n")


def test_explicit_mapping_uses_operator_choices() -> None:
    result = parse_csv(
        b"Work Address,Org,Person\na@example.com,Northwind,Avery Stone\n",
        max_rows=MAX_ROWS,
        column_map={
            "Work Address": "email",
            "Org": "company",
            "Person": "full_name",
        },
    )
    row = result.rows[0]
    assert row.email == "a@example.com"
    assert row.company == "Northwind"
    assert (row.first_name, row.last_name) == ("Avery", "Stone")


def test_explicit_mapping_requires_email() -> None:
    with pytest.raises(CsvFormatError, match="No email column"):
        parse_csv(
            b"Org,Person\nNorthwind,Avery\n",
            max_rows=MAX_ROWS,
            column_map={"Org": "company", "Person": "first_name"},
        )


def test_duplicate_field_mapping_is_rejected() -> None:
    with pytest.raises(CsvFormatError, match="more than one"):
        parse_csv(
            b"Email,Work Email\na@example.com,b@example.com\n",
            max_rows=MAX_ROWS,
            column_map={"Email": "email", "Work Email": "email"},
        )


def test_company_column_is_optional() -> None:
    result = parse("Email,First Name\na@example.com,Avery\n")
    assert result.rows[0].company == ""


def test_blank_company_cell_yields_empty_company() -> None:
    result = parse("Email,Company\na@example.com,\nb@example.com,Northwind\n")
    assert result.rows[0].company == ""
    assert result.rows[1].company == "Northwind"


def test_website_and_industry_columns_are_mapped() -> None:
    result = parse(
        "Email,Company,Website,Industry\n"
        "a@example.com,Northwind,https://northwind.example,Insurance\n"
    )
    row = result.rows[0]
    assert row.website == "https://northwind.example"
    assert row.industry == "Insurance"
    assert build_column_map(["Email", "Company Website", "Sector"]) == {
        "email": 0,
        "website": 1,
        "industry": 2,
    }


def test_company_and_contact_note_headers_map_separately() -> None:
    result = parse(
        "Email,Company,Contact Notes,Company Notes\n"
        "a@example.com,Northwind,Met at AusCERT,Uses a shared vendor\n"
    )
    row = result.rows[0]
    assert row.contact_notes == "Met at AusCERT"
    assert row.company_notes == "Uses a shared vendor"
    assert build_column_map(["Email", "Contact Note", "Company Note"]) == {
        "email": 0,
        "contact_notes": 1,
        "company_notes": 2,
    }


def test_company_linkedin_url_header_maps_to_linkedin() -> None:
    result = parse(
        "Email,Company,company_linkedin_url\n"
        "a@example.com,Northwind,https://www.linkedin.com/company/northwind\n"
    )
    assert result.rows[0].linkedin_url == "https://www.linkedin.com/company/northwind"
    assert build_column_map(["Email", "Company LinkedIn"]) == {
        "email": 0,
        "linkedin_url": 1,
    }


def test_company_size_header_maps_to_size() -> None:
    result = parse(
        "Email,Company,company_size\n"
        "a@example.com,Northwind,11-25\n"
    )
    assert result.rows[0].size == "11-25"
    assert build_column_map(["Email", "Employees", "Headcount"]) == {
        "email": 0,
        "size": 1,
    }


def test_company_location_header_maps_to_location() -> None:
    result = parse(
        "Email,Company,company_location\n"
        "a@example.com,Northwind,Sydney\n"
    )
    assert result.rows[0].location == "Sydney"
    assert build_column_map(["Email", "Company Location", "City"]) == {
        "email": 0,
        "location": 1,
    }


def test_preview_suggests_aliases() -> None:
    preview = preview_csv(b"Work Email,Company Name,Lead Score\n")
    assert preview.headers == ["Work Email", "Company Name", "Lead Score"]
    assert preview.suggestions["Work Email"] == "email"
    assert preview.suggestions["Company Name"] == "company"
    assert preview.suggestions["Lead Score"] is None


def test_empty_file_is_rejected() -> None:
    with pytest.raises(CsvFormatError, match="empty"):
        parse("   \n")


def test_rows_without_an_email_are_counted_not_imported() -> None:
    result = parse("Email,First Name\na@example.com,Avery\n,Blank\n  ,Spaces\n")
    assert [r.email for r in result.rows] == ["a@example.com"]
    assert result.missing_email == 2


# ------------------------------------------------------------------ dedupe ----
def test_duplicates_within_the_file_are_skipped_case_insensitively() -> None:
    result = parse(
        "Email,First Name\n"
        "Avery@Example.com,Avery\n"
        "avery@example.com,Duplicate\n"
        "AVERY@EXAMPLE.COM,Also duplicate\n"
    )
    assert [r.email for r in result.rows] == ["avery@example.com"]
    assert result.rows[0].first_name == "Avery", "the first occurrence wins"


# ------------------------------------------------------------- row contents ----
def test_full_row_is_mapped() -> None:
    result = parse(
        "Work Email,First Name,Last,Company,Job Title,hook,Notes,Source\n"
        "avery.stone@northwind.example,Avery,Stone,Northwind Mutual,CISO,"
        "CPS 234 uplift,Published address,https://example.com/leadership\n"
    )
    row = result.rows[0]
    assert (row.email, row.first_name, row.last_name) == (
        "avery.stone@northwind.example",
        "Avery",
        "Stone",
    )
    assert (row.company, row.title) == ("Northwind Mutual", "CISO")
    assert row.hook == "CPS 234 uplift"
    assert row.source == "https://example.com/leadership"
    assert row.line_number == 2


def test_bom_and_crlf_are_tolerated() -> None:
    result = parse_csv(
        "﻿Email,First Name\r\navery@example.com,Avery\r\n".encode(),
        max_rows=MAX_ROWS,
    )
    assert result.rows[0].email == "avery@example.com"
    assert result.rows[0].first_name == "Avery"


def test_quoted_commas_survive() -> None:
    result = parse('Email,Contact Notes\na@example.com,"Spoke at AusCERT, on the record"\n')
    assert result.rows[0].contact_notes == "Spoke at AusCERT, on the record"


def test_blank_lines_are_ignored() -> None:
    result = parse("Email\na@example.com\n\n\nb@example.com\n")
    assert len(result.rows) == 2


def test_short_rows_do_not_raise() -> None:
    """A row with fewer cells than headers yields empty strings, not IndexError."""
    result = parse("Email,First Name,Company\na@example.com\n")
    assert result.rows[0].first_name == ""
    assert result.rows[0].company == ""


def test_latin1_fallback_for_non_utf8_bytes() -> None:
    result = parse_csv(b"Email,First Name\na@example.com,Elodi\xe9\n", max_rows=MAX_ROWS)
    assert result.rows[0].first_name == "Elodié"


def test_utf8_names_are_preserved() -> None:
    result = parse("Email,First Name\ne.laurent@example.com,Élodie\n")
    assert result.rows[0].first_name == "Élodie"


# -------------------------------------------------------------- name splitting ----
def test_full_name_is_split_when_no_first_last_columns() -> None:
    result = parse("Email,Name\na@example.com,Avery Stone\n")
    assert (result.rows[0].first_name, result.rows[0].last_name) == ("Avery", "Stone")


def test_explicit_first_last_wins_over_full_name() -> None:
    result = parse("Email,Name,First Name,Last\na@example.com,Ignored Entirely,Avery,Stone\n")
    assert (result.rows[0].first_name, result.rows[0].last_name) == ("Avery", "Stone")


@pytest.mark.parametrize(
    ("full", "expected"),
    [
        ("Avery Stone", ("Avery", "Stone")),
        ("Avery", ("Avery", "")),
        ("Avery van der Stone", ("Avery", "van der Stone")),
        ("  ", ("", "")),
    ],
)
def test_split_full_name(full: str, expected: tuple[str, str]) -> None:
    assert split_full_name(full) == expected


# ------------------------------------------------------------------- limits ----
def test_row_cap_truncates_and_reports() -> None:
    body = "".join(f"user{i}@example.com\n" for i in range(10))
    result = parse(f"Email\n{body}", max_rows=4)
    assert len(result.rows) == 4
    assert result.truncated is True


# ------------------------------------------------------- email normalisation ----
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Avery@Example.COM ", "avery@example.com"),
        ("Avery Stone <avery@example.com>", "avery@example.com"),
        ("mailto:avery@example.com", "avery@example.com"),
        ('"avery@example.com"', "avery@example.com"),
        ("avery @ example.com", "avery@example.com"),
        ("", ""),
    ],
)
def test_normalize_email(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected
