"""FastAPI application factory and entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from tradingagents_web.api import health
from tradingagents_web.config import Settings


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Re-issue the session cookie with a fresh max-age on every successful
    response, so the browser cookie expiry slides in lockstep with the DB row.
    """

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


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="TradingAgents Web",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
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
    from tradingagents_web.api import auth as auth_api
    app.include_router(auth_api.router)
    from tradingagents_web.api import runs as runs_api
    app.include_router(runs_api.router)
    from tradingagents_web.api import holdings as holdings_api
    app.include_router(holdings_api.router)
    from tradingagents_web.api import schedules as schedules_api
    app.include_router(schedules_api.router)
    return app


app = create_app()
