"""
Project activity (audit trail) endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.db.models import ActivityLog, Project

router = APIRouter()


@router.get("/project/{project_id}")
def get_project_activity(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of activity entries to return"),
    db: Session = Depends(get_db),
):
    """
    Get recent activity log entries for a project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    entries: List[ActivityLog] = (
        db.query(ActivityLog)
        .filter(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "project_id": str(project_id),
        "activity": [
            {
                "id": str(entry.id),
                "actor": entry.actor,
                "action": entry.action,
                "details": entry.details or {},
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in entries
        ],
    }



