"""
Upload OpenAPI/Swagger specification endpoint.
"""
import json
import logging
import yaml
import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, HttpUrl

from app.db.database import get_db
from app.db.models import Project
from app.services.openapi_parser import OpenAPIParser

logger = logging.getLogger(__name__)

router = APIRouter()


class URLUploadRequest(BaseModel):
    """Request model for URL-based upload."""
    url: str
    project_name: str


async def fetch_spec_from_url(url: str) -> dict:
    """Fetch and parse OpenAPI spec from URL."""
    try:
        # Validate URL format
        if not url or not url.strip():
            raise HTTPException(status_code=400, detail="URL cannot be empty")
        
        # Ensure URL starts with http:// or https://
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
            
            if not content:
                raise HTTPException(status_code=400, detail="Empty response from URL")
            
            # Try JSON first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try YAML
                try:
                    return yaml.safe_load(content)
                except yaml.YAMLError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="Request timeout: URL did not respond within 30 seconds")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"HTTP error {e.response.status_code}: Failed to fetch from URL"
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch from URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching spec from URL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching spec: {str(e)}")


async def parse_spec_content(content: bytes, filename: Optional[str] = None) -> dict:
    """Parse OpenAPI spec content (JSON or YAML)."""
    try:
        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try YAML
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse spec: {str(e)}")


@router.post("/url")
async def upload_spec_from_url(
    request: URLUploadRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Fetch and parse OpenAPI/Swagger specification from URL.
    
    Args:
        request: URL and project name
        db: Database session
    
    Returns:
        Project information with parsed spec
    """
    if not request.project_name or not request.project_name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        # Fetch spec from URL
        logger.info(f"Fetching OpenAPI spec from URL: {request.url}")
        spec_dict = await fetch_spec_from_url(request.url)
        
        if not spec_dict:
            raise HTTPException(status_code=400, detail="Failed to parse specification from URL")
        
        # Parse and validate OpenAPI spec
        logger.info("Parsing OpenAPI specification")
        parser = OpenAPIParser(spec_dict=spec_dict)
        resolved_spec = parser.parse()
        
        if not resolved_spec:
            raise HTTPException(status_code=400, detail="Failed to resolve OpenAPI specification")
        
        # Extract metadata
        info = resolved_spec.get('info', {})
        description = info.get('description', '')
        
        # Store in database
        # TODO: Get user_id from authentication
        user_id = UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
        
        logger.info(f"Creating project: {request.project_name.strip()}")
        project = Project(
            user_id=user_id,
            name=request.project_name.strip(),
            description=description,
            openapi_spec=resolved_spec,
            original_file_name=request.url
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Get endpoints summary
        endpoints = parser.get_endpoints()
        
        logger.info(f"Successfully created project {project.id} with {len(endpoints)} endpoints")
        
        return {
            "project_id": str(project.id),
            "name": project.name,
            "description": project.description,
            "endpoints_count": len(endpoints),
            "endpoints": [
                {
                    "path": ep['path'],
                    "method": ep['method'],
                    "operation_id": ep['operation_id']
                }
                for ep in endpoints[:10]  # Limit to 10 for preview
            ],
            "collections_count": len(parser.get_schemas()),
            "message": "Specification fetched and parsed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing URL upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process specification: {str(e)}"
        )


@router.post("/")
async def upload_spec(
    file: Optional[UploadFile] = File(None),
    project_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload and parse OpenAPI/Swagger specification.
    
    Args:
        file: OpenAPI JSON/YAML file
        project_name: Name for the project (required)
        db: Database session
    
    Returns:
        Project information with parsed spec
    """
    if not project_name or not project_name.strip():
        raise HTTPException(status_code=400, detail="Project name is required")
    
    if not file:
        raise HTTPException(status_code=400, detail="File is required")
    
    try:
        # Read file content
        content = await file.read()
        
        # Parse JSON or YAML
        spec_dict = await parse_spec_content(content, file.filename)
        
        # Parse and validate OpenAPI spec
        parser = OpenAPIParser(spec_dict=spec_dict)
        resolved_spec = parser.parse()
        
        # Extract metadata
        info = resolved_spec.get('info', {})
        description = info.get('description', '')
        
        # Store in database
        # TODO: Get user_id from authentication
        user_id = UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
        
        project = Project(
            user_id=user_id,
            name=project_name.strip(),
            description=description,
            openapi_spec=resolved_spec,
            original_file_name=file.filename
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # Get endpoints summary
        endpoints = parser.get_endpoints()
        
        return {
            "project_id": str(project.id),
            "name": project.name,
            "description": project.description,
            "endpoints_count": len(endpoints),
            "endpoints": [
                {
                    "path": ep['path'],
                    "method": ep['method'],
                    "operation_id": ep['operation_id']
                }
                for ep in endpoints[:10]  # Limit to 10 for preview
            ],
            "collections_count": len(parser.get_schemas()),
            "message": "Specification uploaded and parsed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process specification: {str(e)}")

