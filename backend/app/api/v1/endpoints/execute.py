"""
Test execution endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Body, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
import asyncio

from app.db.database import get_db
from app.db.models import TestSuite, TestExecution, ProjectConfig
from app.services.test_executor import TestExecutor
from app.core.security import decrypt_data
from datetime import datetime

router = APIRouter()


class SingleTestRequest(BaseModel):
    """Request model for single test execution."""
    test_case: Dict[str, Any]
    modified_payload: Optional[Dict[str, Any]] = None
    modified_headers: Optional[Dict[str, str]] = None
    modified_assertions: Optional[List[Dict[str, Any]]] = None


@router.post("/single")
def execute_single_test(
    request: SingleTestRequest = Body(...),
    test_suite_id: str = Query(..., description="Test suite ID"),
    db: Session = Depends(get_db)
):
    """
    Execute a single test case with optional modifications.
    
    Args:
        request: Single test request with test case and optional modifications
        test_suite_id: Test suite ID (passed as query parameter)
        db: Database session
    """
    # Get test suite ID from query param
    if not test_suite_id:
        raise HTTPException(status_code=400, detail="test_suite_id is required as query parameter")
    
    try:
        suite_id = UUID(test_suite_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid test_suite_id format")
    
    test_suite = db.query(TestSuite).filter(TestSuite.id == suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    # Get project config
    config = db.query(ProjectConfig).filter(
        ProjectConfig.project_id == test_suite.project_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=400,
            detail=f"Project configuration not found for project {test_suite.project_id}. Please save config via /api/v1/config/{test_suite.project_id} (Base URL/auth)."
        )
    
    # Prepare test case with modifications
    test_case = request.test_case.copy()
    if request.modified_payload is not None:
        test_case['payload'] = request.modified_payload
    if request.modified_headers is not None:
        test_case['headers'] = {**(test_case.get('headers', {})), **request.modified_headers}
    if request.modified_assertions is not None:
        test_case['assertions'] = request.modified_assertions
    
    # Initialize executor
    executor = TestExecutor(
        base_url=config.base_url,
        auth_type=config.auth_type,
        auth_credentials=config.auth_credentials
    )
    
    # Execute test
    result = executor.execute_test(test_case)
    
    return {
        "test_case": test_case,
        "result": result,
        "executed_at": datetime.utcnow().isoformat()
    }


@router.post("/{test_suite_id}")
def execute_tests(
    test_suite_id: UUID,
    background_tasks: BackgroundTasks,
    request_body: Optional[dict] = Body(default=None),
    db: Session = Depends(get_db)
):
    """
    Execute a test suite or selected test cases.
    
    Args:
        test_suite_id: Test suite ID
        background_tasks: Background tasks
        request_body: Optional body with test_indices list
        db: Database session
    """
    test_indices = None
    if request_body and isinstance(request_body, dict):
        test_indices = request_body.get('test_indices')
    
    # Get test suite
    test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    # Get project config
    config = db.query(ProjectConfig).filter(
        ProjectConfig.project_id == test_suite.project_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=400,
            detail=f"Project configuration not found for project {test_suite.project_id}. Please save config via /api/v1/config/{test_suite.project_id} (Base URL/auth)."
        )
    
    # Filter test cases if indices provided
    test_cases_to_execute = test_suite.test_cases or []
    if test_indices and isinstance(test_indices, list):
        # Filter out None values and ensure indices are valid integers
        valid_indices = [i for i in test_indices if isinstance(i, int) and 0 <= i < len(test_cases_to_execute)]
        if valid_indices:
            test_cases_to_execute = [test_cases_to_execute[i] for i in valid_indices]
        else:
            raise HTTPException(status_code=400, detail="No valid test cases selected")
    
    # Create execution record
    execution = TestExecution(
        test_suite_id=test_suite_id,
        status="running"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Execute in background
    background_tasks.add_task(
        _execute_test_suite,
        execution.id,
        test_cases_to_execute,
        config
    )
    
    return {
        "execution_id": str(execution.id),
        "status": "running",
        "message": f"Test execution started for {len(test_cases_to_execute)} test(s)",
        "test_count": len(test_cases_to_execute)
    }


@router.get("/{execution_id}")
def get_execution_results(execution_id: UUID, db: Session = Depends(get_db)):
    """Get test execution results."""
    execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Get suite to expose project linkage for integrations
    test_suite = db.query(TestSuite).filter(TestSuite.id == execution.test_suite_id).first()
    project_id = str(test_suite.project_id) if test_suite and test_suite.project_id else None

    return {
        "execution_id": str(execution.id),
        "test_suite_id": str(execution.test_suite_id),
        "project_id": project_id,
        "status": execution.status,
        "summary": execution.summary,
        "results": execution.results,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
    }


@router.get("/{execution_id}/stream")
async def stream_execution_results(execution_id: UUID, db: Session = Depends(get_db)):
    """
    Stream execution results via Server-Sent Events (SSE).
    """
    async def event_generator():
        from app.db.database import SessionLocal
        
        db_session = SessionLocal()
        try:
            last_result_count = 0
            
            while True:
                execution = db_session.query(TestExecution).filter(
                    TestExecution.id == execution_id
                ).first()
                
                if not execution:
                    yield f"data: {json.dumps({'error': 'Execution not found'})}\n\n"
                    break
                
                # Get current results
                current_results = execution.results or []
                current_count = len(current_results)
                # Resolve project id for integrations
                suite = db_session.query(TestSuite).filter(
                    TestSuite.id == execution.test_suite_id
                ).first()
                project_id = str(suite.project_id) if suite and suite.project_id else None
                
                # Send update if results changed
                if current_count > last_result_count or execution.status != 'running':
                    update = {
                        "execution_id": str(execution.id),
                        "test_suite_id": str(execution.test_suite_id),
                        "project_id": project_id,
                        "status": execution.status,
                        "summary": execution.summary,
                        "results": current_results,
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    }
                    yield f"data: {json.dumps(update)}\n\n"
                    last_result_count = current_count
                    
                    # Stop if completed
                    if execution.status in ['completed', 'failed']:
                        break
                
                await asyncio.sleep(0.5)  # Poll every 500ms
        
        finally:
            db_session.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


def _execute_test_suite(execution_id: UUID, test_cases: list, config):
    """Execute test suite in background."""
    from app.db.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Initialize executor
        executor = TestExecutor(
            base_url=config.base_url,
            auth_type=config.auth_type,
            auth_credentials=config.auth_credentials
        )
        
        # Execute tests with progress updates
        results = []
        total = len(test_cases)
        passed = 0
        failed = 0
        errors = 0
        
        for i, test_case in enumerate(test_cases):
            try:
                result = executor.execute_test(test_case)
                results.append(result)
                
                if result['status'] == 'passed':
                    passed += 1
                elif result['status'] == 'failed':
                    failed += 1
                else:
                    errors += 1
                
                # Update execution record with progress
                execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
                if execution:
                    execution.results = results
                    execution.summary = {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "errors": errors,
                        "progress": i + 1
                    }
                    db.commit()
            
            except Exception as e:
                errors += 1
                results.append({
                    'test_name': test_case.get('name', 'Unknown'),
                    'status': 'error',
                    'error': str(e)
                })
        
        # Final update
        execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
        if execution:
            execution.status = "completed"
            execution.results = results
            execution.summary = {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors
            }
            execution.completed_at = datetime.utcnow()
            db.commit()
    
    except Exception as e:
        # Update execution with error
        execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
        if execution:
            execution.status = "failed"
            execution.summary = {"error": str(e)}
            execution.completed_at = datetime.utcnow()
            db.commit()
    
    finally:
        db.close()
