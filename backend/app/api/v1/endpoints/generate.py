"""
Test generation endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Body, Header
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Project, ProjectConfig, TestSuite
from app.services.openapi_parser import OpenAPIParser
from app.services.test_generator import TestGenerator
from app.services.activity_logger import log_activity

router = APIRouter()


class EndpointFilter(BaseModel):
    """Endpoint filter model."""
    path: str
    method: str


class GenerateTestsRequest(BaseModel):
    """Request model for test generation."""
    selected_endpoints: Optional[List[EndpointFilter]] = None
    # Optional list of test types to generate, e.g. ["happy_path", "negative", "boundary", "security", "performance"]
    test_types: Optional[List[str]] = None


@router.post("/{project_id}")
def generate_tests(
    project_id: UUID,
    test_format: str = "pytest",
    request_body: Optional[GenerateTestsRequest] = Body(None),
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """
    Generate test cases for a project.
    
    Args:
        project_id: Project ID
        test_format: Output format (pytest, postman)
        request_body: Optional request body with selected endpoints
        db: Database session
    """
    # Get project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get configuration (required for generation)
    config = db.query(ProjectConfig).filter(
        ProjectConfig.project_id == project_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Project configuration not found for project {project_id}. "
                f"Please configure the project first (UI: /projects/{project_id}/config or API: /api/v1/config/{project_id}) "
                f"with at least a Base URL (and auth if needed) before generating tests."
            )
        )
    
    # Require LLM config for LLM-enhanced generation (non-local providers).
    # Local provider (Ollama) does not need an API key.
    llm_provider_check = (config.llm_provider or "openai") if config else "openai"
    if llm_provider_check != "local":
        # Check if LLM API key is configured (either in database or environment)
        has_key_in_db = config and config.llm_api_key and config.llm_api_key.strip()
        if not has_key_in_db:
            # Fallback to environment variable
            from app.core.config import settings
            has_key_in_env = settings.LLM_API_KEY and settings.LLM_API_KEY.strip()
            if not has_key_in_env:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"LLM API key not found. Please configure it in Project Configuration "
                        f"(UI: /projects/{project_id}/config or API: /api/v1/config/{project_id}) "
                        f"or set LLM_API_KEY in your .env file for provider: {llm_provider_check}"
                    ),
                )
    
    # Parse OpenAPI spec
    parser = OpenAPIParser(spec_dict=project.openapi_spec)
    parser.parse()
    
    # Initialize test generator
    llm_api_key = None
    llm_provider = "openai"
    llm_model = "gpt-4"
    llm_endpoint = None
    
    import logging
    logger = logging.getLogger(__name__)
    
    if config:
        llm_provider = config.llm_provider or "openai"
        llm_model = config.llm_model or "gpt-4"
        llm_endpoint = config.llm_endpoint
        
        # For local provider, API key is not needed
        if llm_provider == 'local':
            llm_api_key = None
            logger.info("Using local LLM provider - no API key needed")
        elif config.llm_api_key:
            # Read LLM API key from database (stored directly, no encryption)
            llm_api_key = config.llm_api_key
            logger.info(f"Using LLM API key from database for provider: {llm_provider}")
        else:
            # Fallback to environment variable if not in database
            from app.core.config import settings
            llm_api_key = settings.LLM_API_KEY
            if not llm_api_key or not llm_api_key.strip():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"LLM API key not found. Please configure it in Project Configuration "
                        f"(UI: /projects/{project_id}/config or API: /api/v1/config/{project_id}) "
                        f"or set LLM_API_KEY in your .env file for provider: {llm_provider}"
                    ),
                )
            logger.info(f"Using LLM API key from environment variable for provider: {llm_provider}")
    
    generator = TestGenerator(
        parser=parser,
        llm_api_key=llm_api_key,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_endpoint=llm_endpoint
    )
    
    # Prepare selected endpoints if provided
    selected_endpoints = None
    if request_body and request_body.selected_endpoints:
        selected_endpoints = [
            {"path": ep.path, "method": ep.method}
            for ep in request_body.selected_endpoints
        ]
    
    # Optional test type filter (e.g., ["happy_path", "negative"])
    enabled_test_types = None
    if request_body and request_body.test_types:
        # Normalize to lowercase for comparison
        enabled_test_types = [t.lower() for t in request_body.test_types]
    
    # Generate tests for selected endpoints and enabled types
    try:
        new_test_cases = generator.generate_all_tests(
            selected_endpoints=selected_endpoints,
            enabled_types=enabled_test_types,
        )
    except RuntimeError as e:
        # Catch LLM generation failures and return proper HTTP error
        error_msg = str(e)
        logger.error(f"Test generation failed: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error during test generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Test generation failed: {str(e)}"
        )
    
    # Check if test suite already exists for this project
    existing_suite = db.query(TestSuite).filter(
        TestSuite.project_id == project_id
    ).order_by(TestSuite.created_at.desc()).first()
    
    if existing_suite:
        # Merge with existing test cases instead of replacing
        existing_test_cases = existing_suite.test_cases or []
        existing_generated_endpoints = existing_suite.generated_endpoints or []
        
        # Create a set of existing endpoint keys for quick lookup
        existing_endpoint_keys = {
            f"{ep.get('method', '').upper()}:{ep.get('endpoint', '')}"
            for ep in existing_generated_endpoints
        }
        
        # Track which endpoints we're generating now
        new_generated_endpoints = []
        if selected_endpoints:
            for ep in selected_endpoints:
                endpoint_key = f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
                if endpoint_key not in existing_endpoint_keys:
                    new_generated_endpoints.append({
                        "path": ep.get('path', ''),
                        "method": ep.get('method', '').upper()
                    })
        else:
            # If no endpoints selected, generate for all endpoints
            all_endpoints = parser.get_endpoints()
            for ep in all_endpoints:
                endpoint_key = f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
                if endpoint_key not in existing_endpoint_keys:
                    new_generated_endpoints.append({
                        "path": ep.get('path', ''),
                        "method": ep.get('method', '').upper()
                    })
        
        # Remove existing test cases for the endpoints we're regenerating
        endpoints_to_regenerate = {
            f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
            for ep in new_generated_endpoints
        }
        
        # Filter out test cases for endpoints being regenerated
        filtered_existing_cases = [
            tc for tc in existing_test_cases
            if f"{tc.get('method', '').upper()}:{tc.get('endpoint', '')}" not in endpoints_to_regenerate
        ]
        
        # Combine filtered existing cases with new cases
        merged_test_cases = filtered_existing_cases + new_test_cases
        
        # Update generated endpoints list
        updated_generated_endpoints = existing_generated_endpoints.copy()
        for new_ep in new_generated_endpoints:
            # Remove if exists, then add (to update)
            updated_generated_endpoints = [
                ep for ep in updated_generated_endpoints
                if not (ep.get('path') == new_ep['path'] and ep.get('method') == new_ep['method'])
            ]
            updated_generated_endpoints.append(new_ep)
        
        # Update existing test suite
        existing_suite.test_cases = merged_test_cases
        existing_suite.generated_endpoints = updated_generated_endpoints
        existing_suite.format = test_format
        existing_suite.status = "generated"
        existing_suite.name = f"Test Suite - {project.name}"
        test_suite = existing_suite
        test_cases = merged_test_cases
        db.commit()
        db.refresh(test_suite)
    else:
        # Create new test suite
        # Track generated endpoints
        generated_endpoints = []
        if selected_endpoints:
            generated_endpoints = [
                {"path": ep.get('path', ''), "method": ep.get('method', '').upper()}
                for ep in selected_endpoints
            ]
        else:
            # Generate for all endpoints
            all_endpoints = parser.get_endpoints()
            generated_endpoints = [
                {"path": ep.get('path', ''), "method": ep.get('method', '').upper()}
                for ep in all_endpoints
            ]
        
        test_suite = TestSuite(
            project_id=project_id,
            name=f"Test Suite - {project.name}",
            test_cases=new_test_cases,
            format=test_format,
            status="generated",
            generated_endpoints=generated_endpoints
        )
        db.add(test_suite)
        db.commit()
        db.refresh(test_suite)
        test_cases = new_test_cases

    # Log activity
    try:
        endpoint_count = 0
        if selected_endpoints:
            endpoint_count = len(selected_endpoints)
        else:
            endpoint_count = len(parser.get_endpoints())
        log_activity(
            db=db,
            project_id=project_id,
            action="generated_tests",
            actor=x_actor,
            details={
                "test_suite_id": str(test_suite.id),
                "test_count": len(test_cases),
                "endpoint_count": endpoint_count,
                "test_format": test_format,
                "enabled_test_types": enabled_test_types,
            },
        )
    except Exception:
        # Activity logging should never break main flow
        pass
    
    # Format output based on format
    if test_format == "postman":
        output = _format_as_postman(test_cases, project, config)
    else:
        output = _format_as_pytest(test_cases, project, config)
    
    return {
        "test_suite_id": str(test_suite.id),
        "test_count": len(test_cases),
        "format": test_format,
        "tests_by_type": _count_by_type(test_cases),
        "output": output[:5000] if isinstance(output, str) else output  # Limit preview
    }


@router.get("/{test_suite_id}/cases")
def get_test_cases(
    test_suite_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get all test cases for a test suite, grouped by type.
    
    Args:
        test_suite_id: Test suite ID
        db: Database session
    """
    test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    # Get project info for breadcrumbs
    project = db.query(Project).filter(Project.id == test_suite.project_id).first()
    project_id = str(test_suite.project_id) if test_suite.project_id else None
    project_name = project.name if project else None
    
    # Group test cases by type
    tests_by_type = {}
    all_tests_with_index = []
    for i, test_case in enumerate(test_suite.test_cases):
        test_type = test_case.get('type', 'unknown')
        if test_type not in tests_by_type:
            tests_by_type[test_type] = []
        
        # Add index for selection
        test_case_with_index = test_case.copy()
        test_case_with_index['index'] = i
        tests_by_type[test_type].append(test_case_with_index)
        all_tests_with_index.append(test_case_with_index)
    
    return {
        "test_suite_id": str(test_suite.id),
        "name": test_suite.name,
        "test_count": len(test_suite.test_cases),
        "test_cases_by_type": tests_by_type,
        "all_test_cases": all_tests_with_index,
        "project_id": project_id,
        "project_name": project_name,
        "generated_endpoints": test_suite.generated_endpoints or [],
        # CI metadata for UI badges
        "last_ci_status": test_suite.last_ci_status,
        "last_ci_provider": test_suite.last_ci_provider,
        "last_ci_run_id": test_suite.last_ci_run_id,
        "last_ci_url": test_suite.last_ci_url,
    }


@router.get("/project/{project_id}/generated-endpoints")
def get_generated_endpoints(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get list of endpoints that have been generated for a project.
    
    Args:
        project_id: Project ID
        db: Database session
    """
    test_suite = db.query(TestSuite).filter(
        TestSuite.project_id == project_id
    ).order_by(TestSuite.created_at.desc()).first()
    
    if not test_suite:
        return {"generated_endpoints": []}
    
    return {
        "generated_endpoints": test_suite.generated_endpoints or []
    }


@router.delete("/{test_suite_id}/endpoints")
def delete_endpoint_tests(
    test_suite_id: UUID,
    endpoints: List[Dict[str, str]] = Body(None),
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """
    Delete test cases for specific endpoints and remove them from generated_endpoints.
    
    Args:
        test_suite_id: Test suite ID
        endpoints: List of endpoints to delete: [{"path": "...", "method": "..."}]
        db: Database session
    """
    test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    if endpoints:
        # Delete specific endpoints
        endpoints_to_delete = {
            f"{ep.get('method', '').upper()}:{ep.get('path', '')}"
            for ep in endpoints
        }
        
        remaining_test_cases = [
            tc for tc in test_suite.test_cases
            if f"{tc.get('method', '').upper()}:{tc.get('endpoint', '')}" not in endpoints_to_delete
        ]
        
        generated_endpoints = test_suite.generated_endpoints or []
        remaining_generated_endpoints = [
            ep for ep in generated_endpoints
            if f"{ep.get('method', '').upper()}:{ep.get('path', '')}" not in endpoints_to_delete
        ]
    else:
        # Delete all test cases and generated endpoints
        remaining_test_cases = []
        remaining_generated_endpoints = []
    
    # Update test suite
    test_suite.test_cases = remaining_test_cases
    test_suite.generated_endpoints = remaining_generated_endpoints
    db.commit()
    db.refresh(test_suite)

    # Log activity
    try:
        deleted_count = len(endpoints) if endpoints else "ALL"
        log_activity(
            db=db,
            project_id=test_suite.project_id,
            action="deleted_endpoint_tests" if endpoints else "deleted_all_tests",
            actor=x_actor,
            details={
                "test_suite_id": str(test_suite.id),
                "deleted_endpoints": endpoints or "ALL",
                "remaining_test_count": len(remaining_test_cases),
            },
        )
    except Exception:
        pass
    
    return {
        "message": "Deleted test cases" if endpoints else "Deleted all test cases",
        "remaining_test_count": len(remaining_test_cases),
        "deleted_endpoints": endpoints or "ALL"
    }


@router.get("/project/{project_id}/latest")
def get_latest_test_suite(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get the latest test suite for a project.
    
    Args:
        project_id: Project ID
        db: Database session
    """
    test_suite = db.query(TestSuite).filter(
        TestSuite.project_id == project_id
    ).order_by(TestSuite.created_at.desc()).first()
    
    if not test_suite:
        raise HTTPException(status_code=404, detail="No test suite found for this project")
    
    # Count tests by type
    tests_by_type = {}
    for test_case in test_suite.test_cases:
        test_type = test_case.get('type', 'unknown')
        tests_by_type[test_type] = tests_by_type.get(test_type, 0) + 1
    
    return {
        "test_suite_id": str(test_suite.id),
        "test_count": len(test_suite.test_cases),
        "format": test_suite.format,
        "tests_by_type": tests_by_type,
        "status": test_suite.status,
        "created_at": test_suite.created_at.isoformat() if test_suite.created_at else None
    }


def _count_by_type(test_cases):
    """Count tests by type."""
    counts = {}
    for test in test_cases:
        test_type = test.get('type', 'unknown')
        counts[test_type] = counts.get(test_type, 0) + 1
    return counts


def _format_as_pytest(test_cases, project, config):
    """Format tests as Pytest script."""
    lines = [
        "import pytest",
        "import requests",
        "",
        f"BASE_URL = '{config.base_url if config else 'YOUR_BASE_URL'}'",
        "",
        "class TestAPI:",
    ]
    
    for i, test in enumerate(test_cases):
        test_name = test.get('name', f'test_{i}').replace(' ', '_').lower()
        method = test.get('method', 'GET')
        endpoint = test.get('endpoint', '')
        payload = test.get('payload', {})
        expected_status = test.get('expected_status', [200])
        
        lines.append(f"    def test_{test_name}(self):")
        lines.append(f"        \"\"\"{test.get('description', '')}\"\"\"")
        lines.append(f"        url = f\"{{BASE_URL}}{endpoint}\"")
        
        if method == 'GET':
            lines.append(f"        response = requests.get(url, params={payload})")
        elif method == 'POST':
            lines.append(f"        response = requests.post(url, json={payload})")
        elif method == 'PUT':
            lines.append(f"        response = requests.put(url, json={payload})")
        elif method == 'DELETE':
            lines.append(f"        response = requests.delete(url)")
        
        lines.append(f"        assert response.status_code in {expected_status}")
        lines.append("")
    
    return "\n".join(lines)


def _format_as_postman(test_cases, project, config):
    """Format tests as Postman collection."""
    collection = {
        "info": {
            "name": f"{project.name} - Test Collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": []
    }
    
    for test in test_cases:
        method = test.get('method', 'GET')
        endpoint = test.get('endpoint', '')
        payload = test.get('payload', {})
        
        item = {
            "name": test.get('name', 'Test'),
            "request": {
                "method": method,
                "url": {
                    "raw": f"{{{{base_url}}}}{endpoint}",
                    "host": ["{{base_url}}"],
                    "path": endpoint.split('/')[1:]
                }
            }
        }
        
        if method in ['POST', 'PUT', 'PATCH'] and payload:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": str(payload),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            }
        
        collection["item"].append(item)
    
    collection["variable"] = [
        {
            "key": "base_url",
            "value": config.base_url if config else "YOUR_BASE_URL"
        }
    ]
    
    return collection
