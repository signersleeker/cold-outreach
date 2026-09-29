"""Google OAuth 2.0 web flow for one Gmail mailbox.

Adapted from kinnatic/apps/backend-core/app/connections/services/google_workspace.py
with the multi-tenant dimension removed. Hand-rolled with httpx rather than
google-auth-oauthlib, matching that precedent.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.app_settings import service as settings_service
from app.gmail.client import GmailClient, GmailCredentials, HttpGmailClient
from app.gmail.constants import (
    CONN_CONNECTED,
    CONN_ERROR,
    GMAIL_SCOPES,
    GOOGLE_AUTH_URL,
    GOOGLE_REVOKE_URL,
    GOOGLE_TOKEN_URL,
    OAUTH_STATE_TTL_MINUTES,
)
from app.gmail.oauth_token import OAuthToken
from app.lib import crypto
from app.lib.clock import Clock, ensure_aware

_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_url: str
    state_secret: str
    encryption_key: str
    frontend_url: str


class OAuthStateError(ValueError):
    pass


class GmailOAuthService:
    def __init__(self, cfg: OAuthConfig, clock: Clock) -> None:
        self.cfg = cfg
        self.clock = clock

    def configured(self) -> bool:
        return bool(
            self.cfg.client_id.strip()
            and self.cfg.client_secret.strip()
            and self.cfg.redirect_url.strip()
            and self.cfg.state_secret.strip()
            and self.cfg.encryption_key.strip()
        )

    # ------------------------------------------------------------- connect ----
    def authorization_url(self) -> str:
        if not self.configured():
            raise RuntimeError(
                "Gmail OAuth is not configured. Set GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET and SECRET_KEY in .env."
            )
        params = {
            "client_id": self.cfg.client_id,
            "redirect_uri": self.cfg.redirect_url,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            # offline + consent is what makes Google return a refresh_token. Without
            # prompt=consent a second grant to an already-authorised account comes
            # back without one, and the connection silently cannot be refreshed.
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": self._sign_state(),
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def handle_callback(self, db: Session, code: str, state: str) -> str:
        """Exchange the code, store tokens, record the mailbox. Returns a redirect URL."""
        frontend = self.cfg.frontend_url.rstrip("/")

        def fail(message: str) -> str:
            return f"{frontend}/settings?gmail=error&message={_quote(message)}"

        try:
            self._parse_state(state)
        except OAuthStateError as exc:
            return fail(f"Invalid OAuth state: {exc}")

        try:
            token = self._exchange_code(code)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator as text
            return fail(f"Token exchange failed: {exc}")

        refresh_token = token.get("refresh_token") or ""
        if not refresh_token:
            return fail(
                "Google did not return a refresh token. Remove Kinnatic Outreach at "
                "myaccount.google.com/permissions, then connect again."
            )

        now = self.clock.now()
        expires_in = token.get("expires_in")
        credentials = GmailCredentials(
            refresh_token=refresh_token,
            client_id=self.cfg.client_id,
            client_secret=self.cfg.client_secret,
            access_token=token.get("access_token") or "",
            expiry=now + dt.timedelta(seconds=int(expires_in)) if expires_in else None,
            scopes=GMAIL_SCOPES,
        )
        try:
            profile = HttpGmailClient(credentials, now=self.clock.now).get_profile()
        except Exception as exc:  # noqa: BLE001
            # Nothing has been stored at this point, so do not tell the operator
            # they are "connected" — the mailbox is not usable and the next
            # attempt starts from scratch.
            return fail(profile_failure_message(exc, self.cfg.client_id))

        if not profile.email_address:
            return fail("Gmail did not report an address for this account.")

        row = self._upsert(
            db,
            email=profile.email_address.lower(),
            refresh_token=refresh_token,
            access_token=credentials.access_token,
            token_expiry=credentials.expiry,
            scopes=token.get("scope") or " ".join(GMAIL_SCOPES),
            now=now,
        )
        settings_service.set_from_email(db, row.email)
        db.commit()
        return f"{frontend}/settings?gmail=connected"

    def disconnect(self, db: Session) -> None:
        """Revoke at Google, then delete the row.

        Revoking first matters: deleting the row without revoking would leave a
        live grant on the Google account with no record of it here.
        """
        row = self.current(db)
        if row is None:
            return
        refresh_token = self._decrypt(row.refresh_token_encrypted)
        if refresh_token:
            try:
                with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                    client.post(GOOGLE_REVOKE_URL, data={"token": refresh_token})
            except httpx.HTTPError:
                # Google being unreachable must not strand a local row the
                # operator is trying to remove.
                pass
        db.delete(row)
        settings_service.set_from_email(db, "")
        db.commit()

    # --------------------------------------------------------------- state ----
    def current(self, db: Session) -> OAuthToken | None:
        return db.scalar(select(OAuthToken).limit(1))

    def is_connected(self, db: Session) -> bool:
        row = self.current(db)
        if row is None:
            return False
        return row.status == CONN_CONNECTED and bool(row.refresh_token_encrypted)

    def client(self, db: Session) -> GmailClient:
        """A Gmail client for the connected mailbox, refreshing tokens as needed."""
        row = self.current(db)
        if row is None or not row.refresh_token_encrypted:
            raise RuntimeError("no Gmail mailbox is connected")

        credentials = GmailCredentials(
            refresh_token=self._decrypt(row.refresh_token_encrypted),
            client_id=self.cfg.client_id,
            client_secret=self.cfg.client_secret,
            access_token=self._decrypt(row.access_token_encrypted),
            expiry=ensure_aware(row.token_expiry) if row.token_expiry else None,
            scopes=GMAIL_SCOPES,
        )

        def persist(creds: GmailCredentials) -> None:
            """Cache the refreshed access token so restarts do not re-refresh."""
            row.access_token_encrypted = self._encrypt(creds.access_token)
            row.token_expiry = creds.expiry
            db.add(row)
            db.commit()

        return HttpGmailClient(credentials, now=self.clock.now, on_refresh=persist)

    def mark_error(self, db: Session, message: str) -> None:
        row = self.current(db)
        if row is None:
            return
        row.status = CONN_ERROR
        row.last_error = message[:1000]
        db.add(row)
        db.commit()

    # ------------------------------------------------------------ internal ----
    def _upsert(
        self,
        db: Session,
        *,
        email: str,
        refresh_token: str,
        access_token: str,
        token_expiry: dt.datetime | None,
        scopes: str,
        now: dt.datetime,
    ) -> OAuthToken:
        row = self.current(db)
        if row is None:
            row = OAuthToken(email=email)
            db.add(row)
        row.email = email
        row.refresh_token_encrypted = self._encrypt(refresh_token)
        row.access_token_encrypted = self._encrypt(access_token)
        row.token_expiry = token_expiry
        row.scopes = scopes
        row.status = CONN_CONNECTED
        row.last_error = ""
        row.last_validated_at = now
        db.flush()
        return row

    def _exchange_code(self, code: str) -> dict:
        if not code:
            raise RuntimeError("no authorization code was returned")
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.cfg.client_id,
                    "client_secret": self.cfg.client_secret,
                    "redirect_uri": self.cfg.redirect_url,
                    "grant_type": "authorization_code",
                },
            )
        if response.status_code >= 300:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
        return response.json()

    def _encrypt(self, value: str) -> str:
        return crypto.encrypt_token(self.cfg.encryption_key, value)

    def _decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return crypto.decrypt_token(self.cfg.encryption_key, value)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "stored Gmail token cannot be decrypted; SECRET_KEY has changed. "
                "Disconnect and reconnect Gmail."
            ) from exc

    def _sign_state(self) -> str:
        expires = self.clock.now() + dt.timedelta(minutes=OAUTH_STATE_TTL_MINUTES)
        raw = json.dumps(
            {"exp": int(expires.timestamp()), "nonce": secrets.token_urlsafe(16)},
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(
            self.cfg.state_secret.encode("utf-8"), raw, hashlib.sha256
        ).digest()
        return f"{_b64(raw)}.{_b64(signature)}"

    def _parse_state(self, value: str) -> dict:
        parts = (value or "").split(".")
        if len(parts) != 2:
            raise OAuthStateError("malformed state")
        try:
            raw = _unb64(parts[0])
            signature = _unb64(parts[1])
        except (ValueError, TypeError) as exc:
            raise OAuthStateError("state is not valid base64") from exc

        expected = hmac.new(self.cfg.state_secret.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise OAuthStateError("signature mismatch")

        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise OAuthStateError("state is not valid JSON") from exc

        if int(payload.get("exp", 0)) < int(self.clock.now().timestamp()):
            raise OAuthStateError("state has expired; start the connect flow again")
        return payload


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _quote(message: str) -> str:
    return quote(message, safe="")


# Google's project number is the leading numeric segment of the OAuth client id.
_PROJECT_ID_RE = re.compile(r"^(\d+)-")

_MAX_ERROR_CHARS = 240


def google_project_number(client_id: str) -> str:
    match = _PROJECT_ID_RE.match(client_id or "")
    return match.group(1) if match else ""


def profile_failure_message(exc: Exception, client_id: str) -> str:
    """Turn a failed first API call into something the operator can act on.

    The raw Google error is a few hundred characters of JSON, and it ends up in a
    URL query string, so it is summarised rather than dumped.
    """
    raw = str(exc)
    lowered = raw.lower()

    if "has not been used in project" in lowered or "accessnotconfigured" in lowered:
        project = google_project_number(client_id)
        where = (
            f"https://console.cloud.google.com/apis/library/gmail.googleapis.com?project={project}"
            if project
            else "Google Cloud console > APIs & Services > Library"
        )
        return (
            "The Gmail API is not enabled for this Google Cloud project, so nothing "
            f"was connected. Enable it at {where}, wait a minute, then connect again."
        )

    if "insufficient" in lowered and "scope" in lowered:
        return (
            "The granted scopes do not include Gmail send/read access. Remove this app at "
            "myaccount.google.com/permissions and connect again, accepting both permissions."
        )

    if "invalid_grant" in lowered:
        return (
            "Google rejected the authorisation code. This usually means the clock is skewed "
            "or the code was already used. Start the connect flow again."
        )

    summary = raw if len(raw) <= _MAX_ERROR_CHARS else raw[:_MAX_ERROR_CHARS] + "…"
    return f"Could not read the Gmail profile, so nothing was connected: {summary}"
