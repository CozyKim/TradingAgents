"""Holdings CRUD API."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Holding, Schedule, User
from tradingagents_web.schemas.holding import (
    HoldingCreate,
    HoldingItem,
    HoldingListResponse,
    HoldingUpdate,
)
from tradingagents_web.services import scheduler as scheduler_module
from tradingagents_web.services.holdings_sync import sync_holding_monitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=HoldingListResponse)
def list_holdings(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> HoldingListResponse:
    rows = db.query(Holding).order_by(Holding.ticker.asc()).all()
    return HoldingListResponse(items=[HoldingItem.model_validate(r) for r in rows])


@router.post(
    "",
    response_model=HoldingItem,
    status_code=status.HTTP_201_CREATED,
)
def create_holding(
    payload: HoldingCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> HoldingItem:
    h = Holding(
        ticker=payload.ticker,
        qty=payload.qty,
        avg_cost=payload.avg_cost,
        notes=payload.notes,
    )
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="ticker already exists")
    db.refresh(h)
    return HoldingItem.model_validate(h)


@router.patch("/{holding_id}", response_model=HoldingItem)
def update_holding(
    holding_id: int,
    payload: HoldingUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> HoldingItem:
    h = db.query(Holding).get(holding_id)
    if h is None:
        raise HTTPException(status_code=404, detail="holding not found")

    monitor_changed = False
    if payload.qty is not None:
        h.qty = payload.qty
    if payload.avg_cost is not None:
        h.avg_cost = payload.avg_cost
    if payload.notes is not None:
        h.notes = payload.notes
    if payload.monitor_enabled is not None and payload.monitor_enabled != h.monitor_enabled:
        h.monitor_enabled = payload.monitor_enabled
        monitor_changed = True

    captured_old_schedule_id: int | None = None
    if monitor_changed and payload.monitor_enabled is False:
        old = (
            db.query(Schedule)
            .filter_by(holding_id=h.id, source="holding")
            .one_or_none()
        )
        captured_old_schedule_id = old.id if old else None

    sched: Schedule | None = None
    if monitor_changed:
        sched = sync_holding_monitor(db, h)
    db.commit()
    db.refresh(h)

    if monitor_changed:
        try:
            sch_svc = scheduler_module.get_scheduler()
        except RuntimeError:
            sch_svc = None
        if sch_svc is not None:
            if sched is not None:
                db.refresh(sched)
                sch_svc.register(sched)
            elif captured_old_schedule_id is not None:
                sch_svc.unregister(captured_old_schedule_id)

    return HoldingItem.model_validate(h)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    holding_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> None:
    h = db.query(Holding).get(holding_id)
    if h is None:
        raise HTTPException(status_code=404, detail="holding not found")

    old = (
        db.query(Schedule)
        .filter_by(holding_id=h.id, source="holding")
        .one_or_none()
    )
    captured_old_schedule_id = old.id if old else None

    h.monitor_enabled = False
    sync_holding_monitor(db, h)
    db.delete(h)
    db.commit()

    if captured_old_schedule_id is not None:
        try:
            sch_svc = scheduler_module.get_scheduler()
        except RuntimeError:
            sch_svc = None
        if sch_svc is not None:
            sch_svc.unregister(captured_old_schedule_id)
    return None
