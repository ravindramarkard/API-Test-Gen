"""
Projects management endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Project

router = APIRouter()


class ProjectUpdate(BaseModel):
    """Project update model."""
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("/")
def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    # TODO: Filter by user_id from auth
    projects = db.query(Project).all()
    
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in projects
    ]


@router.get("/{project_id}")
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    """Get project details."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get endpoints
    try:
        from app.services.openapi_parser import OpenAPIParser
        parser = OpenAPIParser(spec_dict=project.openapi_spec)
        parser.parse()  # Parse the spec first
        endpoints = parser.get_endpoints()
    except Exception as e:
        # If parsing fails, return empty endpoints list
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to parse endpoints for project {project_id}: {str(e)}")
        endpoints = []
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "endpoints": [
            {
                "path": ep['path'],
                "method": ep['method'],
                "operation_id": ep['operation_id'],
                "summary": ep.get('summary', '')
            }
            for ep in endpoints
        ],
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


@router.put("/{project_id}")
def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update project name and/or description."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update fields if provided
    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description
    
    db.commit()
    db.refresh(project)
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "message": "Project updated successfully"
    }


@router.delete("/{project_id}")
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a project and all associated data."""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete associated test suites and executions
    from app.db.models import TestSuite, TestExecution
    test_suites = db.query(TestSuite).filter(TestSuite.project_id == project_id).all()
    
    for test_suite in test_suites:
        # Delete test executions for this suite
        db.query(TestExecution).filter(TestExecution.test_suite_id == test_suite.id).delete()
        # Delete the test suite
        db.delete(test_suite)
    
    # Delete project config
    from app.db.models import ProjectConfig
    db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).delete()
    
    # Delete the project
    db.delete(project)
    db.commit()
    
    return {
        "message": "Project deleted successfully",
        "project_id": str(project_id)
    }

