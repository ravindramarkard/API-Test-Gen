"""
Projects management endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Header, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
import yaml
import httpx
import logging

from app.db.database import get_db
from app.db.models import Project, TestSuite
from app.services.openapi_parser import OpenAPIParser
from app.api.v1.endpoints.generate import (
    generate_tests,
    GenerateTestsRequest,
    EndpointFilter,
)
from app.api.v1.endpoints.execute import execute_tests
from app.services.activity_logger import log_activity

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.post("/{project_id}/auto-new-endpoints")
def auto_generate_new_endpoints(
    project_id: UUID,
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """
    Generate tests only for newly added endpoints in the OpenAPI spec for this project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse current spec to discover all endpoints
    parser = OpenAPIParser(spec_dict=project.openapi_spec)
    parser.parse()
    all_endpoints = parser.get_endpoints()
    all_keys = {
        f"{ep['method'].upper()}:{ep['path']}"
        for ep in all_endpoints
    }

    # Find latest test suite for this project and its generated endpoints
    latest_suite: Optional[TestSuite] = (
        db.query(TestSuite)
        .filter(TestSuite.project_id == project_id)
        .order_by(TestSuite.created_at.desc())
        .first()
    )

    existing_keys = set()
    if latest_suite:
        if latest_suite.generated_endpoints:
            for ep in latest_suite.generated_endpoints:
                key = f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
                existing_keys.add(key)
        else:
            # Fallback: infer from test_cases if generated_endpoints is empty
            for tc in latest_suite.test_cases or []:
                key = f"{tc.get('method', '').upper()}:{tc.get('endpoint', '')}"
                existing_keys.add(key)

    # New endpoints are those present in spec but not yet in generated_endpoints
    new_keys = all_keys - existing_keys
    new_endpoints = [
        ep
        for ep in all_endpoints
        if f"{ep['method'].upper()}:{ep['path']}" in new_keys
    ]

    if not new_endpoints:
        return {
            "project_id": str(project_id),
            "has_new": False,
            "message": "No new endpoints found in OpenAPI spec.",
            "test_suite_id": str(latest_suite.id) if latest_suite else None,
        }

    # Build request body for generate_tests (only new endpoints)
    endpoint_filters = [
        EndpointFilter(path=ep["path"], method=ep["method"])
        for ep in new_endpoints
    ]
    gen_request = GenerateTestsRequest(selected_endpoints=endpoint_filters, test_types=None)

    # Delegate to existing generate_tests logic (handles config + LLM checks)
    gen_response = generate_tests(
        project_id=project_id,
        test_format="pytest",
        request_body=gen_request,
        db=db,
        x_actor=x_actor,
    )

    # Log auto-generation specific activity
    try:
        log_activity(
            db=db,
            project_id=project_id,
            action="auto_generated_new_endpoints",
            actor=x_actor,
            details={
                "test_suite_id": gen_response.get("test_suite_id"),
                "test_count": gen_response.get("test_count"),
                "new_endpoint_count": len(new_endpoints),
            },
        )
    except Exception:
        pass

    return {
        "project_id": str(project_id),
        "has_new": True,
        "new_endpoints": [
            {"path": ep["path"], "method": ep["method"]}
            for ep in new_endpoints
        ],
        "generation": gen_response,
    }


@router.post("/{project_id}/autogen-and-run-new")
def auto_generate_and_run_new(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """
    Generate tests for newly added endpoints AND immediately execute those tests.

    Designed for CI/cron usage:
      - Detects endpoints in OpenAPI not yet covered by the latest test suite.
      - Generates tests only for those endpoints.
      - Executes just the newly generated tests.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    parser = OpenAPIParser(spec_dict=project.openapi_spec)
    parser.parse()
    all_endpoints = parser.get_endpoints()

    all_keys = {
        f"{ep['method'].upper()}:{ep['path']}"
        for ep in all_endpoints
    }

    latest_suite: Optional[TestSuite] = (
        db.query(TestSuite)
        .filter(TestSuite.project_id == project_id)
        .order_by(TestSuite.created_at.desc())
        .first()
    )

    existing_keys = set()
    if latest_suite:
        if latest_suite.generated_endpoints:
            for ep in latest_suite.generated_endpoints:
                key = f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
                existing_keys.add(key)
        else:
            for tc in latest_suite.test_cases or []:
                key = f"{tc.get('method', '').upper()}:{tc.get('endpoint', '')}"
                existing_keys.add(key)

    new_keys = all_keys - existing_keys
    new_endpoints = [
        ep
        for ep in all_endpoints
        if f"{ep['method'].upper()}:{ep['path']}" in new_keys
    ]

    if not new_endpoints:
        return {
            "project_id": str(project_id),
            "has_new": False,
            "message": "No new endpoints found in OpenAPI spec.",
            "execution": None,
        }

    # Generate tests only for new endpoints
    endpoint_filters = [
        EndpointFilter(path=ep["path"], method=ep["method"])
        for ep in new_endpoints
    ]
    gen_request = GenerateTestsRequest(selected_endpoints=endpoint_filters, test_types=None)
    gen_response = generate_tests(
        project_id=project_id,
        test_format="pytest",
        request_body=gen_request,
        db=db,
        x_actor=x_actor,
    )

    test_suite_id_str = gen_response.get("test_suite_id")
    if not test_suite_id_str:
        raise HTTPException(
            status_code=500,
            detail="Test generation did not return a test_suite_id",
        )

    suite_id = UUID(test_suite_id_str)
    suite: Optional[TestSuite] = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Generated test suite not found")

    # Determine indices of tests belonging to newly generated endpoints
    new_endpoint_keys = {
        f"{ep['method'].upper()}:{ep['path']}"
        for ep in new_endpoints
    }
    test_indices: List[int] = []
    for idx, tc in enumerate(suite.test_cases or []):
        key = f"{tc.get('method', '').upper()}:{tc.get('endpoint', '')}"
        if key in new_endpoint_keys:
            test_indices.append(idx)

    # Fallback: if something went wrong, execute all tests in the suite
    request_body: Optional[Dict[str, Any]] = None
    if test_indices:
        request_body = {"test_indices": test_indices}

    exec_response = execute_tests(
        test_suite_id=suite_id,
        background_tasks=background_tasks,
        request_body=request_body,
        db=db,
    )

    # Log combined activity
    try:
        log_activity(
            db=db,
            project_id=project_id,
            action="auto_generated_and_executed_new_endpoints",
            actor=x_actor,
            details={
                "test_suite_id": test_suite_id_str,
                "test_count": gen_response.get("test_count"),
                "new_endpoint_count": len(new_endpoints),
                "execution_id": exec_response.get("execution_id"),
                "selected_test_indices": test_indices,
            },
        )
    except Exception:
        pass

    return {
        "project_id": str(project_id),
        "has_new": True,
        "new_endpoints": [
            {"path": ep["path"], "method": ep["method"]}
            for ep in new_endpoints
        ],
        "generation": gen_response,
        "execution": exec_response,
    }


class AddEndpointRequest(BaseModel):
    """Request model for adding endpoints manually."""
    url: Optional[str] = None
    raw_text: Optional[str] = None
    curl_command: Optional[str] = None


async def fetch_spec_from_url(url: str) -> dict:
    """Fetch and parse OpenAPI spec from URL."""
    try:
        if not url or not url.strip():
            raise HTTPException(status_code=400, detail="URL cannot be empty")
        
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


def parse_raw_text(content: str) -> dict:
    """Parse OpenAPI spec from raw text (JSON or YAML)."""
    try:
        if not content or not content.strip():
            raise HTTPException(status_code=400, detail="Raw text cannot be empty")
        
        content = content.strip()
        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try YAML
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing raw text: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse spec: {str(e)}")


def parse_curl_command(curl_cmd: str) -> dict:
    """
    Parse a cURL command and convert it to an OpenAPI path definition.
    
    Example:
        curl -X GET "https://api.example.com/users" -H "accept: application/json"
    """
    import re
    from urllib.parse import urlparse
    
    if not curl_cmd or not curl_cmd.strip():
        raise HTTPException(status_code=400, detail="cURL command cannot be empty")
    
    curl_cmd = curl_cmd.strip()
    
    # Remove 'curl' prefix if present
    if curl_cmd.lower().startswith('curl'):
        curl_cmd = curl_cmd[4:].strip()
    
    # Extract HTTP method (-X flag)
    method_match = re.search(r'-X\s+(\w+)', curl_cmd, re.IGNORECASE)
    method = method_match.group(1).upper() if method_match else 'GET'
    
    # Extract URL (first quoted string or first http/https URL)
    url_match = re.search(r'["\']?https?://[^\s"\']+["\']?', curl_cmd)
    if not url_match:
        # Try without quotes
        url_match = re.search(r'https?://[^\s]+', curl_cmd)
    
    if not url_match:
        raise HTTPException(status_code=400, detail="Could not extract URL from cURL command")
    
    url = url_match.group(0).strip('"\'')
    
    # Parse URL to extract path
    parsed_url = urlparse(url)
    path = parsed_url.path or '/'
    
    # Extract headers (-H flags)
    headers = {}
    header_pattern = r'-H\s+["\']([^"\']+):\s*([^"\']+)["\']'
    for match in re.finditer(header_pattern, curl_cmd):
        header_name = match.group(1).strip()
        header_value = match.group(2).strip()
        headers[header_name] = header_value
    
    # Also try without quotes
    header_pattern2 = r'-H\s+([^:\s]+):\s*([^\s-]+)'
    for match in re.finditer(header_pattern2, curl_cmd):
        header_name = match.group(1).strip()
        header_value = match.group(2).strip()
        # Skip if already found in quoted pattern
        if header_name not in headers:
            headers[header_name] = header_value
    
    # Extract data/body (-d or --data flags)
    data = None
    data_match = re.search(r'(-d|--data)\s+["\']?([^"\']+)["\']?', curl_cmd, re.IGNORECASE)
    if data_match:
        data_str = data_match.group(2).strip()
        # Try to parse as JSON
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = data_str
    
    # Extract query parameters from URL
    query_params = []
    if parsed_url.query:
        from urllib.parse import parse_qs
        query_dict = parse_qs(parsed_url.query)
        for key, values in query_dict.items():
            query_params.append({
                'name': key,
                'in': 'query',
                'required': False,
                'schema': {
                    'type': 'string',
                    'default': values[0] if values else ''
                }
            })
    
    # Build OpenAPI operation
    operation = {
        'operationId': f"{method.lower()}_{path.replace('/', '_').replace('{', '').replace('}', '').strip('_')}",
        'summary': f"{method} {path}",
        'responses': {
            '200': {
                'description': 'Success',
                'content': {
                    'application/json': {
                        'schema': {'type': 'object'}
                    }
                }
            }
        }
    }
    
    # Add headers as parameters
    if headers:
        for header_name, header_value in headers.items():
            # Skip common headers that are handled by OpenAPI
            if header_name.lower() not in ['content-type', 'accept', 'authorization']:
                operation.setdefault('parameters', []).append({
                    'name': header_name,
                    'in': 'header',
                    'required': False,
                    'schema': {
                        'type': 'string',
                        'default': header_value
                    }
                })
    
    # Add query parameters
    if query_params:
        operation.setdefault('parameters', []).extend(query_params)
    
    # Add request body if data exists
    if data and method in ['POST', 'PUT', 'PATCH']:
        content_type = headers.get('Content-Type', headers.get('content-type', 'application/json'))
        operation['requestBody'] = {
            'required': True,
            'content': {
                content_type: {
                    'schema': {
                        'type': 'object' if isinstance(data, dict) else 'string',
                        'example': data
                    }
                }
            }
        }
    
    # Build minimal OpenAPI spec
    openapi_spec = {
        'openapi': '3.0.0',
        'info': {
            'title': 'Imported from cURL',
            'version': '1.0.0'
        },
        'paths': {
            path: {
                method.lower(): operation
            }
        }
    }
    
    return openapi_spec


@router.post("/{project_id}/add-endpoints")
async def add_endpoints_manually(
    project_id: UUID,
    request: AddEndpointRequest = Body(...),
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """
    Add endpoints to an existing project by fetching from URL or parsing raw OpenAPI text.
    Merges new paths into the existing OpenAPI spec.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get spec from URL, raw text, or cURL command
    new_spec_dict = None
    if request.url:
        new_spec_dict = await fetch_spec_from_url(request.url)
    elif request.raw_text:
        new_spec_dict = parse_raw_text(request.raw_text)
    elif request.curl_command:
        new_spec_dict = parse_curl_command(request.curl_command)
    else:
        raise HTTPException(status_code=400, detail="Either 'url', 'raw_text', or 'curl_command' must be provided")
    
    if not new_spec_dict:
        raise HTTPException(status_code=400, detail="Failed to parse specification")
    
    # Parse and validate the new spec
    try:
        new_parser = OpenAPIParser(spec_dict=new_spec_dict)
        new_resolved_spec = new_parser.parse()
        
        if not new_resolved_spec:
            raise HTTPException(status_code=400, detail="Failed to resolve OpenAPI specification")
    except Exception as e:
        logger.error(f"Error parsing new spec: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse specification: {str(e)}")
    
    # Get existing spec
    existing_spec = project.openapi_spec
    if not existing_spec:
        raise HTTPException(status_code=400, detail="Project has no existing OpenAPI spec")
    
    # Merge paths from new spec into existing spec
    existing_paths = existing_spec.get('paths', {})
    new_paths = new_resolved_spec.get('paths', {})
    
    # Track added endpoints
    added_endpoints = []
    merged_paths = {**existing_paths}
    
    for path, path_item in new_paths.items():
        if path not in merged_paths:
            # New path - add it
            merged_paths[path] = path_item
            # Extract methods for this path
            for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                if method in path_item:
                    added_endpoints.append({
                        'path': path,
                        'method': method.upper(),
                        'operation_id': path_item[method].get('operationId', f"{method.upper()}_{path}"),
                        'summary': path_item[method].get('summary', '')
                    })
        else:
            # Path exists - merge methods
            existing_path_item = merged_paths[path]
            for method, operation in path_item.items():
                if method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                    if method not in existing_path_item:
                        # New method for existing path
                        existing_path_item[method] = operation
                        added_endpoints.append({
                            'path': path,
                            'method': method.upper(),
                            'operation_id': operation.get('operationId', f"{method.upper()}_{path}"),
                            'summary': operation.get('summary', '')
                        })
                    # If method exists, we skip it (don't overwrite)
    
    # Merge schemas/components if they exist
    existing_components = existing_spec.get('components', {})
    new_components = new_resolved_spec.get('components', {})
    
    if new_components:
        if not existing_components:
            existing_spec['components'] = {}
        
        # Merge schemas
        existing_schemas = existing_components.get('schemas', {})
        new_schemas = new_components.get('schemas', {})
        if new_schemas:
            if not existing_schemas:
                existing_components['schemas'] = {}
            existing_components['schemas'].update(new_schemas)
        
        # Merge other component types (parameters, responses, etc.)
        for component_type in ['parameters', 'responses', 'requestBodies', 'headers', 'securitySchemes']:
            existing_items = existing_components.get(component_type, {})
            new_items = new_components.get(component_type, {})
            if new_items:
                if not existing_items:
                    existing_components[component_type] = {}
                existing_components[component_type].update(new_items)
    
    # Update the spec with merged paths
    existing_spec['paths'] = merged_paths
    
    # Update project
    project.openapi_spec = existing_spec
    db.commit()
    db.refresh(project)
    
    # Log activity
    try:
        log_activity(
            db=db,
            project_id=project_id,
            action="added_endpoints_manually",
            actor=x_actor,
            details={
                "count": len(added_endpoints),
                "endpoints": added_endpoints,
                "source": "url" if request.url else ("raw_text" if request.raw_text else "curl")
            }
        )
    except Exception as e:
        logger.warning(f"Failed to log activity: {str(e)}")
    
    return {
        "success": True,
        "message": f"Successfully added {len(added_endpoints)} endpoint(s) to project",
        "added_endpoints": added_endpoints,
        "total_endpoints": len(merged_paths)
    }

