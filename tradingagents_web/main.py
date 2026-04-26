"""FastAPI application factory and entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from tradingagents_web.api import alerts as alerts_api
from tradingagents_web.api import auth as auth_api
from tradingagents_web.api import health
from tradingagents_web.api import holdings as holdings_api
from tradingagents_web.api import prices as prices_api
from tradingagents_web.api import runs as runs_api
from tradingagents_web.api import schedules as schedules_api
from tradingagents_web.api import settings_notifications as settings_notifications_api
from tradingagents_web.config import Settings
from tradingagents_web.db import SessionLocal
from tradingagents_web.services import auto_runner
from tradingagents_web.services import scheduler as scheduler_module
from tradingagents_web.services.scheduler import SchedulerService


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Slide the session cookie expiry on every successful response."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        token = request.cookies.get(self._settings.session_cookie_name)
        if token and response.status_code < 400:
            response.set_cookie(
                key=self._settings.session_cookie_name,
                value=token,
                max_age=self._settings.session_max_age_seconds,
                httponly=True,
                secure=self._settings.cookie_secure,
                samesite="strict",
                path="/",
            )
        return response


def _build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = SchedulerService(
            tz=settings.schedule_tz,
            grace_seconds=settings.scheduler_grace_seconds,
        )
        svc.set_trigger_callback(auto_runner.trigger_run)
        scheduler_module.set_scheduler(svc)
        svc.start()
        db = SessionLocal()
        try:
            svc.bootstrap(db)
        finally:
            db.close()
        try:
            yield
        finally:
            svc.shutdown()
            scheduler_module.set_scheduler(None)

    return lifespan


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="TradingAgents Web",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_build_lifespan(settings),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionRefreshMiddleware, settings=settings)
    app.include_router(health.router)
    app.include_router(auth_api.router)
    app.include_router(alerts_api.router)
    app.include_router(holdings_api.router)
    app.include_router(prices_api.router)
    app.include_router(runs_api.router)
    app.include_router(schedules_api.router)
    app.include_router(settings_notifications_api.router)
    return app


app = create_app()
