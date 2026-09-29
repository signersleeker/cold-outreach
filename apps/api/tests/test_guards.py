"""Source-scan guards.

These turn design rules into failing builds rather than comments someone can
quietly violate later.

Each guard inspects *code*, not prose: comments and docstrings are stripped
first, because several of them legitimately name the very things being banned in
order to explain why they are absent.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def python_files(*subpaths: str) -> list[Path]:
    roots = [APP / p for p in subpaths] if subpaths else [APP]
    files: list[Path] = []
    for root in roots:
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    assert files, f"no python files found under {roots}"
    return files


def code_only(path: Path) -> str:
    """The file with comments and docstrings removed.

    String literals in general are kept — a real `msg["List-Unsubscribe"] = ...`
    must still be caught. Only docstrings (a bare string expression statement)
    and `#` comments are dropped.
    """
    source = path.read_text()

    docstring_spans: set[tuple[int, int]] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstring_spans.add((body[0].lineno, body[0].end_lineno or body[0].lineno))

    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and any(
            start <= token.start[0] <= end for start, end in docstring_spans
        ):
            continue
        kept.append(token.string)
    # Joined with spaces, not newlines, so token sequences like `msg [ "To" ] =`
    # stay on one line for the regexes below.
    return " ".join(kept)


def imported_modules(path: Path) -> set[str]:
    """Top-level package names this file imports."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


# ------------------------------------------------------- never SMTP-probe ----
def test_validation_never_opens_an_smtp_connection() -> None:
    """Probing a prospect's mail server is how a sending IP gets blocklisted."""
    banned_calls = (re.compile(r"\bSMTP\s*\("), re.compile(r"\bport\s*=\s*(25|465|587)\b"))
    for path in python_files("validation"):
        assert not {"smtplib", "aiosmtplib", "smtpd"} & imported_modules(path), (
            f"{path.name} imports an SMTP library"
        )
        code = code_only(path)
        for pattern in banned_calls:
            assert not pattern.search(code), f"{path.name} looks like an SMTP probe"


def test_nothing_in_the_app_sends_mail_over_smtp() -> None:
    """Mail leaves only through the Gmail API."""
    for path in python_files():
        offending = {"smtplib", "aiosmtplib", "smtpd"} & imported_modules(path)
        assert not offending, f"{path.relative_to(APP)} imports {offending}"


# --------------------------------------------------- no ESP SDKs anywhere ----
FORBIDDEN_SDKS = {
    "resend",
    "sendgrid",
    "sendinblue",
    "mailgun",
    "boto3",
    "botocore",
    "postmark",
    "mailchimp",
    "mandrill",
    "sparkpost",
}


def test_no_email_service_provider_sdk_is_imported() -> None:
    """Checked by import, not by substring: "x-mailgun-tag" appears in our own
    forbidden-header blocklist and must not trip this."""
    for path in python_files():
        offending = FORBIDDEN_SDKS & imported_modules(path)
        assert not offending, f"{path.relative_to(APP)} imports {offending}"


def test_requirements_pins_no_esp_sdk() -> None:
    requirements = (APP.parent / "requirements.txt").read_text().lower()
    declared = {
        re.split(r"[<>=\[; ]", line.strip())[0]
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert not FORBIDDEN_SDKS & declared, f"requirements.txt pins {FORBIDDEN_SDKS & declared}"


# ----------------------------------------------- all "now" goes via a Clock ----
NAIVE_NOW = (
    re.compile(r"datetime\.now\("),
    re.compile(r"\bdate\.today\("),
    re.compile(r"\butcnow\("),
)

# clock.py is the one place allowed to read the wall clock. Everything else
# receives a Clock, which is what makes the Brisbane cap testable.
CLOCK_EXEMPT = {"lib/clock.py"}


def test_wall_clock_reads_are_confined_to_clock_py() -> None:
    offenders: list[str] = []
    for path in python_files():
        rel = str(path.relative_to(APP))
        if rel in CLOCK_EXEMPT:
            continue
        code = code_only(path)
        for pattern in NAIVE_NOW:
            if pattern.search(code):
                offenders.append(f"{rel}: {pattern.pattern}")
    assert offenders == [], f"read the wall clock directly instead of a Clock: {offenders}"


def test_current_date_sql_is_never_used_for_the_cap() -> None:
    """CURRENT_DATE depends on the server's TimeZone setting, so it is untestable."""
    for path in python_files("sends"):
        assert "CURRENT_DATE" not in code_only(path), f"{path.name} uses CURRENT_DATE"


# -------------------------------------------- no tracking or bulk headers ----
# gmail/constants.py defines the blocklist itself; gmail/mime.py asserts against it.
HEADER_GUARD_EXEMPT = {"gmail/constants.py", "gmail/mime.py"}


def test_no_bulk_or_tracking_header_is_constructed() -> None:
    banned = ("list-unsubscribe", "list-id", "precedence", "x-mailer", "auto-submitted")
    for path in python_files():
        if str(path.relative_to(APP)) in HEADER_GUARD_EXEMPT:
            continue
        lowered = code_only(path).lower()
        for header in banned:
            assert header not in lowered, f"{path.relative_to(APP)} mentions {header}"


def test_mime_module_sets_only_the_expected_headers() -> None:
    """The header set is fixed, so adding one is a deliberate, visible change."""
    code = code_only(APP / "gmail" / "mime.py")
    assigned = set(re.findall(r'msg\s*\[\s*"([^"]+)"\s*\]\s*=', code))
    assert assigned == {"To", "From", "Reply-To", "Subject", "Message-ID", "Date"}


def test_the_outgoing_message_keeps_html_only_for_the_gmail_signature() -> None:
    """Body stays plain; only gmail/mime.py builds the HTML alternative for the signature.

    app/inbox/parsing.py legitimately reads text/html out of *incoming* replies.
    """
    mime = APP / "gmail" / "mime.py"
    for path in [*python_files("gmail"), *python_files("sends"), *python_files("templates")]:
        if path.resolve() == mime.resolve():
            continue
        code = code_only(path).lower()
        assert "text/html" not in code, f"{path.relative_to(APP)} builds an HTML part"
        assert 'subtype = "html"' not in code
        assert "add_alternative" not in code, "no multipart/alternative outside mime.py"

    mime_code = code_only(mime).lower()
    assert "add_alternative" in mime_code
    assert 'subtype = "html"' in mime_code
