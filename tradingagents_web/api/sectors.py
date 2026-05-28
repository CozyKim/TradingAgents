"""/api/sectors — sector CRUD endpoints.

Patterns mirror tradingagents_web/api/alerts.py for consistency:
get_current_user dependency, OrmSession Annotated, sync route handlers.
Run-trigger and SSE endpoints land in Task 15.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Sector, SectorReport, User
from tradingagents_web.schemas.sector import SectorCreate, SectorOut

router = APIRouter(prefix="/api/sectors", tags=["sectors"])


def _to_out(sector: Sector, db: OrmSession) -> SectorOut:
    """Attach latest report metadata to a Sector row for list/detail responses."""
    latest = db.execute(
        select(SectorReport)
        .where(SectorReport.sector_id == sector.id)
        .order_by(desc(SectorReport.version))
        .limit(1)
    ).scalar_one_or_none()
    return SectorOut(
        id=sector.id,
        slug=sector.slug,
        name=sector.name,
        description=sector.description,
        keywords=sector.keywords,
        is_preset=sector.is_preset,
        created_at=sector.created_at,
        latest_report_version=latest.version if latest else None,
        latest_report_at=latest.created_at if latest else None,
    )


@router.get("", response_model=list[SectorOut])
async def list_sectors(
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return all sectors (presets + user-created) with latest report meta."""
    sectors = db.execute(select(Sector).order_by(Sector.id)).scalars().all()
    return [_to_out(s, db) for s in sectors]


@router.post("", response_model=SectorOut, status_code=status.HTTP_201_CREATED)
async def create_sector(
    payload: SectorCreate,
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    _xhr: Annotated[None, Depends(require_xhr)] = None,
):
    """Create a user-defined sector. Slug is auto-derived from name when omitted."""
    sector = Sector(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        keywords=payload.keywords,
        is_preset=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sector)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"slug '{payload.slug}' already exists",
        ) from None
    db.refresh(sector)
    return _to_out(sector, db)


@router.delete("/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sector(
    sector_id: int,
    db: Annotated[OrmSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    _xhr: Annotated[None, Depends(require_xhr)] = None,
):
    """Delete a user-created sector. Presets are protected (409)."""
    sector = db.get(Sector, sector_id)
    if sector is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sector not found")
    if sector.is_preset:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "preset sectors cannot be deleted",
        )
    db.delete(sector)
    db.commit()
    return None
