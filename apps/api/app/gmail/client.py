"""Gmail REST client.

Pure httpx. An OAuth refresh is one POST to Google's token endpoint, so there is
no reason to pull in google-auth (which drags in `requests` for its transport)
just to do it. Keeping the whole surface to four calls also makes the client
trivially fakeable in tests.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.gmail.constants import GMAIL_API_BASE, GOOGLE_TOKEN_URL
from app.gmail.exceptions import GmailAmbiguousError, GmailPermanentError

_TIMEOUT_SECONDS = 30.0

# Refresh a little early rather than discovering expiry mid-request.
_EXPIRY_SKEW = dt.timedelta(seconds=60)


@dataclass(frozen=True)
class GmailProfile:
    email_address: str
    messages_total: int


@dataclass
class GmailCredentials:
    """Everything needed to mint an access token for the connected mailbox."""

    refresh_token: str
    client_id: str
    client_secret: str
    access_token: str = ""
    expiry: dt.datetime | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def is_fresh(self, now: dt.datetime) -> bool:
        if not self.access_token or self.expiry is None:
            return False
        return now + _EXPIRY_SKEW < self.expiry


class GmailClient(Protocol):
    def get_profile(self) -> GmailProfile: ...

    def send(self, raw: str) -> str: ...

    def list_message_ids(self, query: str, max_results: int = 100) -> list[str]: ...

    def get_message(self, message_id: str) -> dict: ...

    def find_by_rfc822_id(self, rfc822_message_id: str) -> str | None: ...


def _raise_for_status(response: httpx.Response, action: str) -> None:
    """Split failures into "definitely not sent" and "cannot tell".

    The daily-cap slot is reserved before the send, so this distinction decides
    whether the slot is given back. See app/gmail/exceptions.py.
    """
    if response.status_code < 300:
        return
    detail = response.text[:500]
    if response.status_code in (408, 429) or response.status_code >= 500:
        raise GmailAmbiguousError(f"{action}: HTTP {response.status_code}: {detail}")
    raise GmailPermanentError(f"{action}: HTTP {response.status_code}: {detail}")


def refresh_access_token(
    credentials: GmailCredentials, *, now: dt.datetime, client: httpx.Client | None = None
) -> GmailCredentials:
    """Exchange the refresh token for a fresh access token."""
    owned = client is None
    http = client or httpx.Client(timeout=_TIMEOUT_SECONDS)
    try:
        response = http.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": credentials.refresh_token,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            },
        )
    except httpx.HTTPError as exc:
        raise GmailAmbiguousError(f"token refresh failed: {exc}") from exc
    finally:
        if owned:
            http.close()

    _raise_for_status(response, "token refresh")
    payload = response.json()
    expires_in = int(payload.get("expires_in") or 0)
    credentials.access_token = str(payload.get("access_token") or "")
    credentials.expiry = now + dt.timedelta(seconds=expires_in) if expires_in else None
    if not credentials.access_token:
        raise GmailPermanentError("token refresh returned no access_token")
    return credentials


class HttpGmailClient:
    """Talks to Gmail as the connected user, refreshing tokens as needed."""

    def __init__(
        self,
        credentials: GmailCredentials,
        *,
        now: Callable[[], dt.datetime],
        on_refresh: Callable[[GmailCredentials], None] | None = None,
    ) -> None:
        self._credentials = credentials
        self._now = now
        self._on_refresh = on_refresh
        self._client = httpx.Client(timeout=_TIMEOUT_SECONDS)

    def _access_token(self) -> str:
        now = self._now()
        if not self._credentials.is_fresh(now):
            refresh_access_token(self._credentials, now=now)
            if self._on_refresh is not None:
                self._on_refresh(self._credentials)
        return self._credentials.access_token

    # ---------------------------------------------------------------- API ----
    def get_profile(self) -> GmailProfile:
        payload = self._request("GET", "/profile").json()
        return GmailProfile(
            email_address=payload.get("emailAddress", ""),
            messages_total=int(payload.get("messagesTotal") or 0),
        )

    def send(self, raw: str) -> str:
        response = self._request("POST", "/messages/send", json={"raw": raw})
        return str(response.json().get("id") or "")

    def list_message_ids(self, query: str, max_results: int = 100) -> list[str]:
        ids: list[str] = []
        for page in self._paginate("/messages", {"q": query, "maxResults": min(max_results, 100)}):
            ids.extend(str(m["id"]) for m in page.get("messages") or [])
            if len(ids) >= max_results:
                break
        return ids[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._request("GET", f"/messages/{message_id}", params={"format": "full"}).json()

    def find_by_rfc822_id(self, rfc822_message_id: str) -> str | None:
        """Resolve a send whose outcome was never observed.

        Gmail's rfc822msgid: search matches the Message-ID we generated before
        sending, which is how an interrupted send is reconciled.
        """
        stripped = rfc822_message_id.strip("<>")
        found = self.list_message_ids(f"rfc822msgid:{stripped}", max_results=1)
        return found[0] if found else None

    # ----------------------------------------------------------- internal ----
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            response = self._client.request(
                method, f"{GMAIL_API_BASE}{path}", params=params, json=json, headers=headers
            )
        except httpx.HTTPError as exc:
            raise GmailAmbiguousError(f"{method} {path}: {exc}") from exc
        _raise_for_status(response, f"{method} {path}")
        return response

    def _paginate(self, path: str, params: dict) -> Iterator[dict]:
        page_token: str | None = None
        while True:
            query = dict(params)
            if page_token:
                query["pageToken"] = page_token
            payload = self._request("GET", path, params=query).json()
            yield payload
            page_token = payload.get("nextPageToken")
            if not page_token:
                return
