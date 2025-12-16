"""
Simple activity logging service for per-project audit trail.
"""
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ActivityLog


def log_activity(
    db: Session,
    project_id: UUID,
    action: str,
    actor: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist a single activity entry.

    Args:
        db: SQLAlchemy session
        project_id: Project UUID
        action: Short action label, e.g. "generated_tests", "deleted_endpoint_tests", "updated_config"
        actor: Optional actor identifier (email, name, or system). If not provided, defaults to "system".
        details: Optional structured metadata about the action (counts, endpoint list, etc.).
    """
    actor_value = actor or "system"
    entry = ActivityLog(
        project_id=project_id,
        actor=actor_value,
        action=action,
        details=details or {},
    )
    db.add(entry)
    db.commit()



