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

