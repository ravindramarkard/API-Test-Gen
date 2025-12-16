"""
API v1 router.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    upload,
    config,
    generate,
    execute,
    projects,
    reports,
    integrations,
    activity,
)

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(generate.router, prefix="/generate", tags=["generate"])
api_router.include_router(execute.router, prefix="/execute", tags=["execute"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])

