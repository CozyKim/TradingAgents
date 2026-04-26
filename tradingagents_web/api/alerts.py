"""Alerts API: list, unread-count, mark read, mark-all-read."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Alert, User
from tradingagents_web.schemas.alert import (
    AlertItem,
    AlertListResponse,
    AlertType,
    UnreadCountResponse,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    type_: Annotated[AlertType | None, Query(alias="type")] = None,
    ticker: str | None = None,
    read: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AlertListResponse:
    """List alerts with optional filters and pagination, newest first.

    Args:
        db: Database session (injected).
        _user: Authenticated user (injected, enforces auth).
        type_: Optional alert type filter.
        ticker: Optional ticker symbol filter (case-insensitive).
        read: Optional read/unread filter.
        page: 1-based page number.
        page_size: Items per page (1–100).

    Returns:
        AlertListResponse with items, total count, page, and page_size.
    """
    page = max(1, page)
    page_size = max(1, min(100, page_size))

    filters = []
    if type_ is not None:
        filters.append(Alert.type == type_.value)
    if ticker:
        filters.append(Alert.ticker == ticker.strip().upper())
    if read is not None:
        filters.append(Alert.read == read)

    base = select(Alert)
    if filters:
        base = base.where(*filters)

    total_stmt = select(func.count()).select_from(Alert)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = db.execute(total_stmt).scalar_one()

    rows = (
        db.execute(
            base.order_by(desc(Alert.created_at), desc(Alert.id))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        .scalars()
        .all()
    )
    return AlertListResponse(
        items=[AlertItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> UnreadCountResponse:
    """Return the number of unread alerts (for the workspace bell badge).

    Args:
        db: Database session (injected).
        _user: Authenticated user (injected, enforces auth).

    Returns:
        UnreadCountResponse with the count of unread alerts.
    """
    count = db.execute(
        select(func.count()).select_from(Alert).where(Alert.read == False)  # noqa: E712
    ).scalar_one()
    return UnreadCountResponse(unread=count)


@router.post("/{alert_id}/read")
def mark_read(
    alert_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    """Mark a single alert as read.

    Args:
        alert_id: Primary key of the alert to mark.
        db: Database session (injected).
        _user: Authenticated user (injected, enforces auth).
        _csrf: XHR CSRF guard (injected).

    Returns:
        {"ok": True} on success.

    Raises:
        HTTPException: 404 if alert not found.
    """
    row = db.get(Alert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    row.read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, int]:
    """Mark all currently-unread alerts as read. Returns count affected.

    Args:
        db: Database session (injected).
        _user: Authenticated user (injected, enforces auth).
        _csrf: XHR CSRF guard (injected).

    Returns:
        {"marked": <int>} with the number of rows updated.
    """
    result = db.execute(
        update(Alert).where(Alert.read == False).values(read=True)  # noqa: E712
    )
    db.commit()
    return {"marked": result.rowcount or 0}
