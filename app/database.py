"""Database engine, session factory, and query helpers for StiebelMonitor."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.models import Base, MachineStatus, Reading

logger = logging.getLogger(__name__)

_engine = None
_SessionFactory: sessionmaker[Session] | None = None


def init_db(config: AppConfig) -> None:
    """Create the engine, session factory, and all tables."""
    global _engine, _SessionFactory
    _engine = create_engine(config.database.url, pool_pre_ping=True)
    _SessionFactory = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)
    logger.info("Database initialised — tables created if needed")


def get_session() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _SessionFactory()


# ── Write operations ────────────────────────────────────────────────────────


def insert_readings(readings: list[dict]) -> None:
    """Bulk-insert a list of reading dicts (tag, register_address, value, timestamp)."""
    with get_session() as session:
        session.add_all([Reading(**r) for r in readings])
        session.commit()


def insert_status(mode: str, timestamp: datetime | None = None) -> None:
    """Insert a machine-status record."""
    with get_session() as session:
        status = MachineStatus(mode=mode)
        if timestamp is not None:
            status.timestamp = timestamp
        session.add(status)
        session.commit()


# ── Read operations ─────────────────────────────────────────────────────────


def get_readings(
    tags: list[str] | None,
    start: datetime | None,
    end: datetime | None,
) -> list[dict]:
    """Return readings filtered by tag(s) and time range."""
    with get_session() as session:
        stmt = select(Reading).order_by(Reading.timestamp)
        if tags:
            stmt = stmt.where(Reading.tag.in_(tags))
        if start:
            stmt = stmt.where(Reading.timestamp >= start)
        if end:
            stmt = stmt.where(Reading.timestamp <= end)

        rows: Sequence[Reading] = session.scalars(stmt).all()
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "tag": r.tag,
                "register_address": r.register_address,
                "value": r.value,
            }
            for r in rows
        ]


def get_latest_readings() -> list[dict]:
    """Return the most recent value for every distinct tag."""
    with get_session() as session:
        # Sub-query: max timestamp per tag
        from sqlalchemy import func

        sub = (
            select(Reading.tag, func.max(Reading.timestamp).label("max_ts"))
            .group_by(Reading.tag)
            .subquery()
        )
        stmt = select(Reading).join(
            sub,
            (Reading.tag == sub.c.tag) & (Reading.timestamp == sub.c.max_ts),
        )
        rows: Sequence[Reading] = session.scalars(stmt).all()
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "tag": r.tag,
                "register_address": r.register_address,
                "value": r.value,
            }
            for r in rows
        ]


def get_latest_status() -> dict | None:
    """Return the most recent machine status record."""
    with get_session() as session:
        stmt = select(MachineStatus).order_by(desc(MachineStatus.timestamp)).limit(1)
        row = session.scalars(stmt).first()
        if row is None:
            return None
        return {"timestamp": row.timestamp.isoformat(), "mode": row.mode}


def get_status_history(
    start: datetime | None, end: datetime | None
) -> list[dict]:
    """Return status changes within the given time range."""
    with get_session() as session:
        stmt = select(MachineStatus).order_by(MachineStatus.timestamp)
        if start:
            stmt = stmt.where(MachineStatus.timestamp >= start)
        if end:
            stmt = stmt.where(MachineStatus.timestamp <= end)

        rows: Sequence[MachineStatus] = session.scalars(stmt).all()
        return [
            {"timestamp": r.timestamp.isoformat(), "mode": r.mode} for r in rows
        ]
