"""Schedules CRUD + run-now API."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Schedule, User
from tradingagents_web.schemas.schedule import (
    ScheduleCreate,
    ScheduleItem,
    ScheduleListResponse,
    ScheduleUpdate,
)
from tradingagents_web.services import auto_runner
from tradingagents_web.services import scheduler as scheduler_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _try_register(s: Schedule) -> None:
    try:
        svc = scheduler_module.get_scheduler()
    except RuntimeError:
        return
    svc.register(s)


def _try_unregister(schedule_id: int) -> None:
    try:
        svc = scheduler_module.get_scheduler()
    except RuntimeError:
        return
    svc.unregister(schedule_id)


def _hydrate(s: Schedule) -> ScheduleItem:
    item = ScheduleItem.model_validate(s)
    try:
        svc = scheduler_module.get_scheduler()
        nxt = svc.next_run(s.id)
        if nxt is not None:
            item = item.model_copy(update={"next_run": nxt})
    except RuntimeError:
        pass
    return item


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ScheduleListResponse:
    rows = db.query(Schedule).order_by(Schedule.created_at.desc()).all()
    return ScheduleListResponse(items=[_hydrate(r) for r in rows])


@router.post(
    "",
    response_model=ScheduleItem,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: ScheduleCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ScheduleItem:
    s = Schedule(
        name=payload.name,
        ticker=payload.ticker,
        cron_expr=payload.cron_expr,
        preset=payload.preset.model_dump(),
        active=payload.active,
        source="user",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    _try_register(s)
    return _hydrate(s)


@router.patch("/{schedule_id}", response_model=ScheduleItem)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ScheduleItem:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    if payload.name is not None:
        s.name = payload.name
    if payload.cron_expr is not None:
        s.cron_expr = payload.cron_expr
    if payload.preset is not None:
        s.preset = payload.preset.model_dump()
    if payload.active is not None:
        s.active = payload.active
    db.commit()
    db.refresh(s)
    if s.active:
        _try_register(s)
    else:
        _try_unregister(s.id)
    return _hydrate(s)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> None:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    _try_unregister(s.id)
    db.delete(s)
    db.commit()
    return None


@router.post("/{schedule_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_now(
    schedule_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, str]:
    s = db.query(Schedule).get(schedule_id)
    if s is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    run_id = await auto_runner.trigger_run(schedule_id)
    if run_id is None:
        raise HTTPException(status_code=409, detail="schedule inactive")
    return {"run_id": run_id}
