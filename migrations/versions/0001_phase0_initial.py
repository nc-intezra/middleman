"""Phase 0 initial schema: gpu, application, holding, event.

Revision ID: 0001_phase0
Revises:
Create Date: 2026-11-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_phase0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gpu",
        sa.Column("gpu_id", sa.String(length=128), primary_key=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("mem_mb", sa.Integer(), nullable=True),
        sa.Column("health", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_gpu_host", "gpu", ["host"])

    op.create_table(
        "application",
        sa.Column("app_id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "holding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gpu_id", sa.String(length=128), sa.ForeignKey("gpu.gpu_id"), nullable=False),
        sa.Column(
            "app_id", sa.String(length=128), sa.ForeignKey("application.app_id"), nullable=False
        ),
        # Phase 0 writes only 'free'/'held'; column is a plain string so later
        # phases add 'granted'/'reclaiming'/'released' with no type migration.
        sa.Column("state", sa.String(length=32), nullable=False, server_default="held"),
        sa.Column("util", sa.Integer(), nullable=True),
        sa.Column("work_id", sa.String(length=255), nullable=True),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("gpu_id", name="uq_holding_gpu"),
    )
    op.create_index("ix_holding_gpu_id", "holding", ["gpu_id"])
    op.create_index("ix_holding_app_id", "holding", ["app_id"])

    op.create_table(
        "event",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("gpu_id", sa.String(length=128), nullable=True),
        sa.Column("app_id", sa.String(length=128), nullable=True),
        sa.Column("detail", sa.String(length=1024), nullable=True),
    )
    op.create_index("ix_event_ts", "event", ["ts"])
    op.create_index("ix_event_kind", "event", ["kind"])
    op.create_index("ix_event_gpu_id", "event", ["gpu_id"])
    op.create_index("ix_event_app_id", "event", ["app_id"])


def downgrade() -> None:
    op.drop_table("event")
    op.drop_table("holding")
    op.drop_table("application")
    op.drop_index("ix_gpu_host", table_name="gpu")
    op.drop_table("gpu")
