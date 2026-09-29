"""Signed session cookie for the single app user.

There is one user and one password, so a session is just a signed, expiring
marker — there is no identity to carry beyond "whoever holds this passed the
password check".
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SALT = "kinnatic-outreach-session"
_SUBJECT = "owner"


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    if not secret_key:
        raise ValueError("SECRET_KEY is required to sign sessions")
    return URLSafeTimedSerializer(secret_key, salt=_SALT)


def issue_session(secret_key: str) -> str:
    return _serializer(secret_key).dumps({"sub": _SUBJECT})


def read_session(secret_key: str, token: str, max_age_seconds: int) -> bool:
    """True when the cookie is a valid, unexpired session we issued."""
    if not token:
        return False
    try:
        payload = _serializer(secret_key).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return isinstance(payload, dict) and payload.get("sub") == _SUBJECT
