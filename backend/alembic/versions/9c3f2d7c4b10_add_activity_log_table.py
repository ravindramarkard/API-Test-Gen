"""add_activity_log_table

Revision ID: 9c3f2d7c4b10
Revises: 8a2b7c1e3ab4
Create Date: 2025-12-15 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "9c3f2d7c4b10"
down_revision = "8a2b7c1e3ab4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create activity_logs table (if it doesn't exist)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'activity_logs' not in tables:
        op.create_table(
            "activity_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("actor", sa.String(length=255), nullable=True),
            sa.Column("action", sa.String(length=255), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_activity_logs_project_id",
            "activity_logs",
            ["project_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_activity_logs_project_id", table_name="activity_logs")
    op.drop_table("activity_logs")


