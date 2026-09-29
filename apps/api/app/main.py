from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.app_settings.router import router as settings_router
from app.auth.router import router as auth_router
from app.auth.service import LoginThrottle
from app.companies.router import router as companies_router
from app.config import get_settings
from app.contacts.router import router as contacts_router
from app.dashboard.router import router as dashboard_router
from app.deps import require_session
from app.gmail.api_router import router as gmail_api_router
from app.gmail.oauth_service import GmailOAuthService, OAuthConfig
from app.gmail.router import router as gmail_oauth_router
from app.inbox.router import router as inbox_router
from app.lib.clock import SystemClock
from app.lib.errors import AppError
from app.lib.response import error_body
from app.sends.router import router as sends_router
from app.sends.services.send import SendService
from app.suppressions.router import router as suppressions_router
from app.templates.groups_router import router as template_groups_router
from app.templates.router import router as templates_router
from app.unsub.router import router as unsub_router
from app.validation.factory import build_validator

API_PREFIX = "/api/v1"

# Session-protected API routers. The OAuth redirect pair and the public
# unsubscribe page are mounted separately and deliberately not gated.
_API_ROUTERS = (
    dashboard_router,
    contacts_router,
    companies_router,
    templates_router,
    template_groups_router,
    sends_router,
    suppressions_router,
    settings_router,
    gmail_api_router,
    inbox_router,
)


def _wire_state(app: FastAPI) -> None:
    settings = get_settings()
    clock = SystemClock()

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

    app.state.settings = settings
    app.state.clock = clock
    app.state.validator = build_validator(settings)
    app.state.gmail_oauth = oauth
    app.state.login_throttle = LoginThrottle()
    app.state.send_service = SendService(settings=settings, oauth=oauth, clock=clock)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import get_engine
    from app.migrations.runner import upgrade

    # Apply any pending migrations on boot (CREATE TABLE IF NOT EXISTS — safe).
    upgrade(get_engine())
    _wire_state(app)
    yield


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA so everything lives on one origin.

    Optional: in development the React dev server proxies to this API instead.
    """
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Kinnatic Outreach", lifespan=lifespan)
    _wire_state(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.resolved_frontend_url()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=12 * 3600,
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return error_body(exc.status_code, *exc.messages)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
            msg = err.get("msg", "invalid")
            messages.append(f"{loc}: {msg}" if loc else msg)
        return error_body(400, *(messages or ["validation failed"]))

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Login itself cannot require a session.
    app.include_router(auth_router, prefix=API_PREFIX)
    for router in _API_ROUTERS:
        app.include_router(router, prefix=API_PREFIX, dependencies=[Depends(require_session)])

    # Root-mounted. /auth/google gates itself; the callback is authenticated by
    # its signed state, and /u/{token} is public by design.
    app.include_router(gmail_oauth_router)
    app.include_router(unsub_router)

    if settings.serve_frontend:
        _mount_frontend(app)

    return app


app = create_app()
