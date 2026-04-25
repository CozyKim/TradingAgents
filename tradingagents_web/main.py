"""FastAPI application factory and entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradingagents_web.api import health
from tradingagents_web.config import Settings


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
    app.include_router(health.router)
    return app


app = create_app()
