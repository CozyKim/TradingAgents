from sqlalchemy import text

from tradingagents_web.db import SessionLocal, engine


def test_engine_is_configured() -> None:
    assert engine is not None
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_factory_yields_session() -> None:
    with SessionLocal() as session:
        result = session.execute(text("SELECT 2")).scalar()
        assert result == 2
