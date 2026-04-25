from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradingagents_web.models import Base, Session as SessionModel, User
from tradingagents_web.models.base import utcnow


def _setup_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_user_can_be_created() -> None:
    db = _setup_db()
    user = User(password_hash="hashed")
    db.add(user)
    db.commit()
    assert user.id == 1
    assert user.created_at is not None


def test_session_links_to_user() -> None:
    db = _setup_db()
    user = User(password_hash="hashed")
    db.add(user)
    db.commit()
    sess = SessionModel(
        id="abc123", user_id=user.id, expires_at=utcnow() + timedelta(days=30)
    )
    db.add(sess)
    db.commit()
    assert sess.user_id == user.id
