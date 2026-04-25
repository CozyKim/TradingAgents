from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradingagents_web.auth import (
    create_session,
    delete_session,
    get_session_by_token,
    sliding_extend,
)
from tradingagents_web.models import Base, Session as SessionModel, User
from tradingagents_web.models.base import utcnow


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(password_hash="x")
    session.add(user)
    session.commit()
    return session


def test_create_session_returns_token(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    assert isinstance(token, str)
    found = db.query(SessionModel).filter_by(id=token).first()
    assert found is not None
    assert found.user_id == user.id


def test_get_session_by_token_returns_none_when_expired(db: Session) -> None:
    user = db.query(User).first()
    expired = SessionModel(
        id="expired", user_id=user.id, expires_at=utcnow() - timedelta(seconds=1)
    )
    db.add(expired)
    db.commit()
    assert get_session_by_token(db, "expired") is None


def test_sliding_extend(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    sess = db.query(SessionModel).filter_by(id=token).first()
    original_exp = sess.expires_at
    sliding_extend(db, sess)
    db.refresh(sess)
    assert sess.expires_at >= original_exp


def test_delete_session(db: Session) -> None:
    user = db.query(User).first()
    token = create_session(db, user.id)
    delete_session(db, token)
    assert db.query(SessionModel).filter_by(id=token).first() is None
