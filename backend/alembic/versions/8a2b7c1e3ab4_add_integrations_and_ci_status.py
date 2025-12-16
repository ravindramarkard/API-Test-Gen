"""add_integrations_and_ci_status

Revision ID: 8a2b7c1e3ab4
Revises: 6524e82f7870
Create Date: 2025-12-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "8a2b7c1e3ab4"
down_revision = "6524e82f7870"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add CI status fields to test_suites (if they don't exist)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    test_suites_columns = [col['name'] for col in inspector.get_columns('test_suites')]
    
    if 'last_ci_status' not in test_suites_columns:
        op.add_column("test_suites", sa.Column("last_ci_status", sa.String(length=50), nullable=True))
    if 'last_ci_provider' not in test_suites_columns:
        op.add_column("test_suites", sa.Column("last_ci_provider", sa.String(length=100), nullable=True))
    if 'last_ci_run_id' not in test_suites_columns:
        op.add_column("test_suites", sa.Column("last_ci_run_id", sa.String(length=255), nullable=True))
    if 'last_ci_url' not in test_suites_columns:
        op.add_column("test_suites", sa.Column("last_ci_url", sa.String(length=1000), nullable=True))

    # Create integration_configs table (if it doesn't exist)
    tables = inspector.get_table_names()
    if 'integration_configs' not in tables:
        op.create_table(
            "integration_configs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("base_url", sa.String(length=500), nullable=True),
            sa.Column("project_key", sa.String(length=255), nullable=True),
            sa.Column("repo_owner", sa.String(length=255), nullable=True),
            sa.Column("repo_name", sa.String(length=255), nullable=True),
            sa.Column("auth_token_encrypted", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        )
        op.create_index(
            "ix_integration_configs_project_id",
            "integration_configs",
            ["project_id"],
        )


def downgrade() -> None:
    # Drop integration_configs table
    op.drop_index("ix_integration_configs_project_id", table_name="integration_configs")
    op.drop_table("integration_configs")

    # Remove CI status fields from test_suites
    op.drop_column("test_suites", "last_ci_url")
    op.drop_column("test_suites", "last_ci_run_id")
    op.drop_column("test_suites", "last_ci_provider")
    op.drop_column("test_suites", "last_ci_status")


