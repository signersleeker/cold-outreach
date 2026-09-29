from __future__ import annotations

import datetime as dt
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.app_settings.app_setting import SETTINGS_ID, AppSetting
from app.config import get_settings
from app.constants import SESSION_COOKIE_NAME
from app.contacts.contact import Contact
from app.contacts.service import new_unsub_token
from app.database import get_db, import_all_models, reset_engine
from app.gmail.constants import CONN_CONNECTED, GMAIL_SCOPES
from app.gmail.oauth_token import OAuthToken
from app.lib import crypto
from app.lib.session import issue_session
from app.sends.services.send import SendService
from app.templates.constants import (
    FIRST_TOUCH_BODY,
    FIRST_TOUCH_SUBJECT,
    FOLLOW_UP_BODY,
    FOLLOW_UP_SUBJECT,
)
from app.templates.template import Template
from tests.fakes import FakeGmailClient, FakeValidator, FrozenClock

ROOT = Path(__file__).resolve().parents[1]

# 2026-03-02 10:00 Brisbane == 2026-03-02T00:00Z. Comfortably mid-day locally, so
# tests that advance a few hours do not accidentally cross the date boundary.
FIXED_NOW = dt.datetime(2026, 3, 2, 0, 0, 0, tzinfo=dt.UTC)


@pytest.fixture(scope="session")
def settings():
    load_dotenv(ROOT / ".env.test", override=True)
    get_settings.cache_clear()
    reset_engine()
    try:
        return get_settings()
    except Exception:
        pytest.skip("DATABASE_URL missing in apps/api/.env.test")


@pytest.fixture(scope="session")
def engine(settings):
    eng = create_engine(settings.sqlalchemy_database_url(), pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip(
            "test database not reachable — run `docker compose up -d` in apps/api "
            "and copy .env.test.example to .env.test"
        )
    import_all_models()
    from app.migrations.runner import upgrade

    upgrade(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """A session whose writes are always rolled back.

    join_transaction_mode="create_savepoint" turns each commit() inside
    production code into a savepoint release rather than a real commit, so code
    that legitimately commits several times (the send path commits three) runs
    unmodified while the outer rollback still erases everything. That means no
    per-table cleanup list to maintain, and a new table needs no change here.
    """
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def committed_db(engine) -> Generator[Session, None, None]:
    """Real commits, for the one test that needs genuine concurrency.

    The savepoint trick above would give a false pass on the counter's ON CONFLICT
    row-lock serialisation, which is only observable across real transactions.
    """
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("TRUNCATE daily_counters"))
        session.commit()
        session.close()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(FIXED_NOW)


@pytest.fixture
def validator() -> FakeValidator:
    return FakeValidator()


@pytest.fixture
def gmail() -> FakeGmailClient:
    return FakeGmailClient()


# ----------------------------------------------------------------- fixtures ----
@pytest.fixture
def app_settings(db: Session) -> AppSetting:
    row = db.get(AppSetting, SETTINGS_ID)
    if row is None:
        row = AppSetting(id=SETTINGS_ID)
        db.add(row)
    row.sender_name = "Joey"
    row.sender_title = "CEO"
    row.company_legal = "Kinnatic Pty Ltd"
    row.from_email = "joey@kinnatic.ai"
    row.daily_cap = 20
    row.include_unsub_link = True
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def connected_gmail(db: Session, settings) -> OAuthToken:
    row = OAuthToken(
        email="joey@kinnatic.ai",
        refresh_token_encrypted=crypto.encrypt_token(settings.secret_key, "fake-refresh-token"),
        scopes=" ".join(GMAIL_SCOPES),
        status=CONN_CONNECTED,
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def template(db: Session) -> Template:
    row = Template(
        name="CISO shadow AI test",
        subject=FIRST_TOUCH_SUBJECT,
        body=FIRST_TOUCH_BODY,
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def follow_up_template(db: Session) -> Template:
    row = Template(name="Follow up test", subject=FOLLOW_UP_SUBJECT, body=FOLLOW_UP_BODY)
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def make_contact(db: Session):
    def _make(**overrides) -> Contact:
        fields = {
            "email": "avery.stone@northwind.example",
            "first_name": "Avery",
            "last_name": "Stone",
            "company": "Northwind Mutual",
            "title": "CISO",
            "hook": "CPS 234 uplift",
            "source": "https://example.com/leadership",
            "validation_status": "valid",
            "unsub_token": new_unsub_token(),
        }
        fields.update(overrides)
        contact = Contact(**fields)
        db.add(contact)
        db.commit()
        return contact

    return _make


@pytest.fixture
def contact(make_contact) -> Contact:
    return make_contact()


@pytest.fixture
def send_service(settings, clock, gmail, db) -> SendService:
    from app.gmail.oauth_service import GmailOAuthService, OAuthConfig

    oauth = GmailOAuthService(
        OAuthConfig(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_url=settings.google_redirect_url(),
            state_secret=settings.secret_key,
            encryption_key=settings.secret_key,
            frontend_url=settings.resolved_frontend_url(),
        ),
        clock,
    )
    return SendService(
        settings=settings, oauth=oauth, clock=clock, client_factory=lambda _db: gmail
    )


@pytest.fixture
def client(db, settings, clock, validator, gmail) -> Generator[TestClient, None, None]:
    """An authenticated TestClient with all external services faked."""
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.state.settings = settings
    app.state.clock = clock
    app.state.validator = validator
    app.state.gmail_client_factory = lambda _db: gmail
    app.state.send_service = SendService(
        settings=settings,
        oauth=app.state.gmail_oauth,
        clock=clock,
        client_factory=lambda _db: gmail,
    )
    app.state.gmail_oauth.clock = clock

    with TestClient(app) as test_client:
        test_client.cookies.set(SESSION_COOKIE_NAME, issue_session(settings.secret_key))
        yield test_client
