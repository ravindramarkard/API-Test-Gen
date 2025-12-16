"""
External integrations (issue trackers, CI status) endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging
import requests
import os

from app.db.database import get_db
from app.db.models import Project, TestSuite, TestExecution, IntegrationConfig
from app.core.security import encrypt_data, decrypt_data

router = APIRouter()

logger = logging.getLogger(__name__)


class IntegrationConfigCreate(BaseModel):
    """Create/update integration configuration for a project."""
    provider: str = Field(..., description="Integration provider, e.g. 'jira' or 'github'")
    base_url: Optional[str] = Field(
        None,
        description="Base URL for provider API (e.g. https://your-domain.atlassian.net or https://api.github.com)",
    )
    project_key: Optional[str] = Field(
        None,
        description="Jira project key (for provider == 'jira')",
    )
    repo_owner: Optional[str] = Field(
        None,
        description="GitHub repository owner (for provider == 'github')",
    )
    repo_name: Optional[str] = Field(
        None,
        description="GitHub repository name (for provider == 'github')",
    )
    auth_token: Optional[str] = Field(
        None,
        description="Access token / PAT (will be stored encrypted; optional if already configured).",
    )


class IntegrationConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider: str
    base_url: Optional[str]
    project_key: Optional[str]
    repo_owner: Optional[str]
    repo_name: Optional[str]
    has_token: bool


class CreateIssueRequest(BaseModel):
    """Request to create an external issue from a failed test."""
    project_id: UUID
    test_suite_id: UUID
    test_execution_id: Optional[UUID] = None
    test_index: Optional[int] = Field(
        None,
        description="Index of the test result within the execution results array. "
        "If omitted, backend will try to infer a failed test.",
    )
    provider: str = Field(..., description="jira or github")
    title: Optional[str] = None
    description: Optional[str] = None


class CreateIssueResponse(BaseModel):
    provider: str
    issue_url: str
    issue_key: Optional[str] = None
    raw_id: Optional[str] = None


class CiStatusUpdateRequest(BaseModel):
    """Webhook payload from CI to update last run status on a test suite."""
    project_id: Optional[UUID] = None
    test_suite_id: UUID
    provider: str = Field(..., description="CI provider identifier, e.g. github_actions")
    status: str = Field(..., description="success | failed | running | unknown")
    run_id: Optional[str] = None
    url: Optional[str] = None


@router.get("/config/{project_id}", response_model=List[IntegrationConfigResponse])
def list_integration_configs(project_id: UUID, db: Session = Depends(get_db)):
    """List non-sensitive integration configs for a project."""
    configs = (
        db.query(IntegrationConfig)
        .filter(IntegrationConfig.project_id == project_id)
        .all()
    )
    return [
        IntegrationConfigResponse(
            id=cfg.id,
            project_id=cfg.project_id,
            provider=cfg.provider,
            base_url=cfg.base_url,
            project_key=cfg.project_key,
            repo_owner=cfg.repo_owner,
            repo_name=cfg.repo_name,
            has_token=bool(cfg.auth_token_encrypted),
        )
        for cfg in configs
    ]


@router.post("/config/{project_id}", response_model=IntegrationConfigResponse)
def create_or_update_integration_config(
    project_id: UUID,
    payload: IntegrationConfigCreate,
    db: Session = Depends(get_db),
):
    """Create or update a Jira/GitHub integration config for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    provider = payload.provider.lower()
    if provider not in ("jira", "github"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported provider. Supported providers: jira, github",
        )

    existing = (
        db.query(IntegrationConfig)
        .filter(
            IntegrationConfig.project_id == project_id,
            IntegrationConfig.provider == provider,
        )
        .first()
    )

    auth_token_encrypted = None
    if payload.auth_token:
        auth_token_encrypted = encrypt_data(payload.auth_token)

    if existing:
        existing.base_url = payload.base_url or existing.base_url
        existing.project_key = payload.project_key or existing.project_key
        existing.repo_owner = payload.repo_owner or existing.repo_owner
        existing.repo_name = payload.repo_name or existing.repo_name
        if auth_token_encrypted:
            existing.auth_token_encrypted = auth_token_encrypted
        db.commit()
        db.refresh(existing)
        cfg = existing
    else:
        cfg = IntegrationConfig(
            project_id=project_id,
            provider=provider,
            base_url=payload.base_url,
            project_key=payload.project_key,
            repo_owner=payload.repo_owner,
            repo_name=payload.repo_name,
            auth_token_encrypted=auth_token_encrypted,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    return IntegrationConfigResponse(
        id=cfg.id,
        project_id=cfg.project_id,
        provider=cfg.provider,
        base_url=cfg.base_url,
        project_key=cfg.project_key,
        repo_owner=cfg.repo_owner,
        repo_name=cfg.repo_name,
        has_token=bool(cfg.auth_token_encrypted),
    )


def _build_issue_markdown(
    project: Project,
    test_suite: TestSuite,
    execution: Optional[TestExecution],
    test_result: Dict[str, Any],
) -> str:
    """Create a markdown body including trace and links."""
    title = test_result.get("test_name") or "API test failure"
    method = test_result.get("method", "")
    endpoint = test_result.get("endpoint", "")
    expected = test_result.get("expected_status")
    actual = test_result.get("actual_status")
    status = test_result.get("status")

    lines = [
        f"# {title}",
        "",
        f"- **Project**: {project.name}",
        f"- **Test Suite**: {test_suite.name}",
        f"- **Endpoint**: `{method} {endpoint}`",
        f"- **Test Status**: `{status}`",
        f"- **Expected Status**: `{expected}`",
        f"- **Actual Status**: `{actual}`",
    ]

    if execution:
        lines.append(f"- **Execution ID**: `{execution.id}`")
        if execution.completed_at:
            lines.append(f"- **Completed At**: `{execution.completed_at.isoformat()}`")

    lines.append("")

    error = test_result.get("error")
    if error:
        lines.append("## Error")
        lines.append("")
        lines.append("```")
        lines.append(str(error))
        lines.append("```")
        lines.append("")

    # Request/response summary
    lines.append("## Request / Response")
    lines.append("")
    request_block = {
        "method": method,
        "endpoint": endpoint,
        "payload": test_result.get("payload"),
        "request_headers": test_result.get("request_headers"),
    }
    response_block = {
        "status": actual,
        "response_body": test_result.get("response_body"),
        "response_headers": test_result.get("response_headers"),
    }
    lines.append("**Request:**")
    lines.append("")
    lines.append("```json")
    try:
        import json as _json

        lines.append(_json.dumps(request_block, indent=2, default=str))
    except Exception:
        lines.append(str(request_block))
    lines.append("```")
    lines.append("")
    lines.append("**Response:**")
    lines.append("")
    lines.append("```json")
    try:
        import json as _json

        lines.append(_json.dumps(response_block, indent=2, default=str))
    except Exception:
        lines.append(str(response_block))
    lines.append("```")

    # Trace steps (for E2E/CRUD etc.)
    trace = test_result.get("trace") or []
    if trace:
        lines.append("")
        lines.append("## Trace")
        lines.append("")
        for idx, step in enumerate(trace, start=1):
            step_title = step.get("name") or f"Step {idx}"
            lines.append(f"### {step_title}")
            lines.append("")
            step_request = {
                "method": step.get("method"),
                "url": step.get("url") or step.get("endpoint"),
                "headers": step.get("request_headers"),
                "query": step.get("request_query"),
                "body": step.get("request_payload") or step.get("request_body"),
            }
            step_response = {
                "status": step.get("response_status"),
                "headers": step.get("response_headers"),
                "body": step.get("response_body"),
            }
            lines.append("**Request:**")
            lines.append("")
            lines.append("```json")
            try:
                import json as _json

                lines.append(_json.dumps(step_request, indent=2, default=str))
            except Exception:
                lines.append(str(step_request))
            lines.append("```")
            lines.append("")
            lines.append("**Response:**")
            lines.append("")
            lines.append("```json")
            try:
                import json as _json

                lines.append(_json.dumps(step_response, indent=2, default=str))
            except Exception:
                lines.append(str(step_response))
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def _select_test_result(results: List[Dict[str, Any]], index: Optional[int]) -> Dict[str, Any]:
    if not results:
        raise HTTPException(status_code=400, detail="Execution has no results to create an issue from")
    if index is not None:
        if index < 0 or index >= len(results):
            raise HTTPException(status_code=400, detail="test_index out of range for execution results")
        return results[index]
    # Prefer failed tests
    for r in results:
        if isinstance(r, dict) and r.get("status") in ("failed", "error"):
            return r
    # Fallback to first
    return results[0]


def _create_jira_issue(cfg: IntegrationConfig, title: str, body: str, token: str) -> CreateIssueResponse:
    if not cfg.base_url or not cfg.project_key:
        raise HTTPException(
            status_code=400,
            detail="Jira integration missing base_url or project_key",
        )
    url = cfg.base_url.rstrip("/") + "/rest/api/3/issue"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "fields": {
            "project": {"key": cfg.project_key},
            "summary": title,
            "description": body,
            "issuetype": {"name": "Bug"},
        }
    }
    logger.info(f"Creating Jira issue at {url} for project {cfg.project_key}")
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code not in (200, 201):
        logger.error(f"Jira issue creation failed: {resp.status_code} {resp.text[:500]}")
        raise HTTPException(
            status_code=400,
            detail=f"Jira issue creation failed: {resp.status_code} - {resp.text[:500]}",
        )
    data = resp.json()
    issue_key = data.get("key")
    browse_url = cfg.base_url.rstrip("/") + f"/browse/{issue_key}" if issue_key else cfg.base_url
    return CreateIssueResponse(
        provider="jira",
        issue_url=browse_url,
        issue_key=issue_key,
        raw_id=str(data.get("id")) if data.get("id") is not None else None,
    )


def _create_github_issue(cfg: IntegrationConfig, title: str, body: str, token: str) -> CreateIssueResponse:
    if not cfg.repo_owner or not cfg.repo_name:
        raise HTTPException(
            status_code=400,
            detail="GitHub integration missing repo_owner or repo_name",
        )
    base_url = cfg.base_url.rstrip("/") if cfg.base_url else "https://api.github.com"
    api_url = f"{base_url}/repos/{cfg.repo_owner}/{cfg.repo_name}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": ["api-test-failure", "auto-generated"],
    }
    logger.info(f"Creating GitHub issue at {api_url} for repo {cfg.repo_owner}/{cfg.repo_name}")
    resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if resp.status_code not in (200, 201):
        logger.error(f"GitHub issue creation failed: {resp.status_code} {resp.text[:500]}")
        raise HTTPException(
            status_code=400,
            detail=f"GitHub issue creation failed: {resp.status_code} - {resp.text[:500]}",
        )
    data = resp.json()
    html_url = data.get("html_url") or data.get("url")
    number = data.get("number")
    return CreateIssueResponse(
        provider="github",
        issue_url=html_url,
        issue_key=str(number) if number is not None else None,
        raw_id=str(number) if number is not None else None,
    )


@router.post("/issues", response_model=CreateIssueResponse)
def create_issue_from_test_failure(
    request: CreateIssueRequest,
    db: Session = Depends(get_db),
):
    """
    Create an external issue (Jira/GitHub) from a failed test, including trace.
    """
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    test_suite = db.query(TestSuite).filter(TestSuite.id == request.test_suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    execution = None
    if request.test_execution_id:
        execution = (
            db.query(TestExecution)
            .filter(TestExecution.id == request.test_execution_id)
            .first()
        )
        if not execution:
            raise HTTPException(status_code=404, detail="Test execution not found")
    else:
        # Use latest execution for this suite if not specified
        execution = (
            db.query(TestExecution)
            .filter(TestExecution.test_suite_id == request.test_suite_id)
            .order_by(TestExecution.started_at.desc())
            .first()
        )
        if not execution:
            raise HTTPException(status_code=404, detail="No executions found for this test suite")

    results = execution.results or []
    test_result = _select_test_result(results, request.test_index)

    provider = request.provider.lower()
    cfg = (
        db.query(IntegrationConfig)
        .filter(
            IntegrationConfig.project_id == request.project_id,
            IntegrationConfig.provider == provider,
        )
        .first()
    )
    if not cfg:
        raise HTTPException(
            status_code=400,
            detail=f"No {provider} integration configured for this project. Configure it in the Integrations section first.",
        )

    if not cfg.auth_token_encrypted:
        raise HTTPException(
            status_code=400,
            detail=f"{provider} integration exists but has no auth token configured. Please update the integration config.",
        )

    try:
        token = decrypt_data(cfg.auth_token_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt integration token: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Stored integration token could not be decrypted. Please re-enter and save the token.",
        )

    default_title = request.title or f"[API Test Failure] {test_result.get('method', '')} {test_result.get('endpoint', '')}"
    body = request.description or _build_issue_markdown(project, test_suite, execution, test_result)

    if provider == "jira":
        return _create_jira_issue(cfg, default_title, body, token)
    if provider == "github":
        return _create_github_issue(cfg, default_title, body, token)

    raise HTTPException(
        status_code=400,
        detail="Unsupported provider. Supported providers: jira, github",
    )


@router.post("/ci/status")
def update_ci_status(
    payload: CiStatusUpdateRequest,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, convert_underscores=False),
):
    """
    CI webhook to update last run status for a test suite.

    CI systems should send a simple JSON payload and authenticate with X-API-Key
    matching BACKEND_CI_STATUS_TOKEN (or CI_STATUS_TOKEN) env var.
    """
    expected_key = os.getenv("BACKEND_CI_STATUS_TOKEN") or os.getenv("CI_STATUS_TOKEN")
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="CI status token not configured on server (BACKEND_CI_STATUS_TOKEN / CI_STATUS_TOKEN)",
        )
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid CI status token")

    suite = db.query(TestSuite).filter(TestSuite.id == payload.test_suite_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Test suite not found")

    # Basic status normalization
    status = payload.status.lower()
    if status not in ("success", "failed", "running", "unknown"):
        status = "unknown"

    suite.last_ci_status = status
    suite.last_ci_provider = payload.provider
    suite.last_ci_run_id = payload.run_id
    suite.last_ci_url = payload.url

    db.commit()
    db.refresh(suite)

    return {
        "test_suite_id": str(suite.id),
        "last_ci_status": suite.last_ci_status,
        "last_ci_provider": suite.last_ci_provider,
        "last_ci_run_id": suite.last_ci_run_id,
        "last_ci_url": suite.last_ci_url,
    }



