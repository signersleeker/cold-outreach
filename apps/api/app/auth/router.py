from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.auth.schemas import LoginRequest, SessionDTO
from app.auth.service import password_matches
from app.constants import SESSION_COOKIE_NAME
from app.lib.errors import AppError
from app.lib.response import data_body
from app.lib.session import issue_session, read_session

router = APIRouter(tags=["auth"])


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request) -> Response:
    settings = request.app.state.settings
    throttle = request.app.state.login_throttle
    key = _client_key(request)

    if not settings.outreach_app_password:
        raise AppError(503, "OUTREACH_APP_PASSWORD is not set in .env")

    if throttle.is_locked(key):
        raise AppError(
            429,
            f"too many failed attempts; try again in {throttle.retry_after_seconds(key)}s",
        )

    if not password_matches(payload.password, settings.outreach_app_password):
        throttle.record_failure(key)
        raise AppError(401, "incorrect password")

    throttle.reset(key)
    response = data_body(SessionDTO(authenticated=True))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        issue_session(settings.secret_key),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return response


@router.post("/auth/logout")
def logout(request: Request) -> Response:
    response = data_body(SessionDTO(authenticated=False))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/auth/session")
def session(request: Request) -> Response:
    settings = request.app.state.settings
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    valid = read_session(settings.secret_key, token, settings.session_max_age_seconds)
    return data_body(SessionDTO(authenticated=valid))
