from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# --- GPU ledger states -------------------------------------------------------
# Phase 0 recognises only `free` and `held`. The later states (granted,
# reclaiming, released) belong to Phase 1, when the broker can actually signal.
# They are listed here so the schema and validation have one source of truth,
# but the contract layer rejects anything outside PHASE0_STATES on write.
STATE_FREE = "free"
STATE_HELD = "held"
STATE_GRANTED = "granted"
STATE_RECLAIMING = "reclaiming"
STATE_RELEASED = "released"

PHASE0_STATES = frozenset({STATE_FREE, STATE_HELD})
ALL_STATES = frozenset(
    {STATE_FREE, STATE_HELD, STATE_GRANTED, STATE_RECLAIMING, STATE_RELEASED}
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Gpu(Base):
    """The pool inventory: one row per physical GPU."""

    __tablename__ = "gpu"

    gpu_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    host: Mapped[str] = mapped_column(String(255), index=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mem_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health: Mapped[str] = mapped_column(String(32), default="unknown")

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    holding: Mapped[Holding | None] = relationship(
        back_populates="gpu", uselist=False, cascade="all, delete-orphan"
    )


class Application(Base):
    """A registered consumer (e.g. flamejob)."""

    __tablename__ = "application"

    app_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    holdings: Mapped[list[Holding]] = relationship(back_populates="application")


class Holding(Base):
    """Who holds each GPU now. One row per GPU (a GPU has at most one holder)."""

    __tablename__ = "holding"
    __table_args__ = (UniqueConstraint("gpu_id", name="uq_holding_gpu"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gpu_id: Mapped[str] = mapped_column(ForeignKey("gpu.gpu_id"), index=True)
    app_id: Mapped[str] = mapped_column(ForeignKey("application.app_id"), index=True)
    state: Mapped[str] = mapped_column(String(32), default=STATE_HELD)
    util: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    gpu: Mapped[Gpu] = relationship(back_populates="holding")
    application: Mapped[Application] = relationship(back_populates="holdings")


class Event(Base):
    """Append-only audit and trace."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    gpu_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    app_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)
