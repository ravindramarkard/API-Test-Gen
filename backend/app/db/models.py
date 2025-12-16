"""
Database models.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.database import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Project(Base):
    """Project model for storing OpenAPI specs."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    openapi_spec = Column(JSON, nullable=False)  # Parsed OpenAPI spec
    original_file_name = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProjectConfig(Base):
    """Project configuration (base URL, auth, LLM settings)."""
    __tablename__ = "project_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    base_url = Column(String(500), nullable=False)
    auth_type = Column(String(50))  # basic, bearer, oauth, api_key
    auth_credentials = Column(Text)  # Encrypted credentials
    llm_provider = Column(String(50))  # openai, xai, etc.
    llm_api_key = Column(Text)  # Encrypted
    llm_endpoint = Column(String(500))  # Optional custom endpoint
    llm_model = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TestSuite(Base):
    """Generated test suite."""
    __tablename__ = "test_suites"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    test_cases = Column(JSON, nullable=False)  # Array of test cases
    format = Column(String(50))  # pytest, postman, etc.
    status = Column(String(50))  # generated, running, completed, failed
    generated_endpoints = Column(JSON)  # List of endpoints that have been generated: [{"path": "...", "method": "..."}]
    # CI status metadata for team workflows
    last_ci_status = Column(String(50))  # success, failed, running, unknown
    last_ci_provider = Column(String(100))  # github_actions, gitlab, jenkins, etc.
    last_ci_run_id = Column(String(255))
    last_ci_url = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TestExecution(Base):
    """Test execution results."""
    __tablename__ = "test_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_suite_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(50))  # running, completed, failed
    results = Column(JSON)  # Test results
    summary = Column(JSON)  # Summary stats
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class IntegrationConfig(Base):
    """External integration configuration per project (Jira, GitHub, etc.)."""
    __tablename__ = "integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # jira, github, etc.
    base_url = Column(String(500))
    project_key = Column(String(255))  # For Jira
    repo_owner = Column(String(255))  # For GitHub
    repo_name = Column(String(255))  # For GitHub
    auth_token_encrypted = Column(Text)  # Encrypted PAT / token
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ActivityLog(Base):
    """Per-project activity log (audit trail)."""
    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    actor = Column(String(255))  # e.g., user email or name
    action = Column(String(255), nullable=False)  # short action label
    details = Column(JSON)  # structured metadata about the action
    created_at = Column(DateTime(timezone=True), server_default=func.now())

