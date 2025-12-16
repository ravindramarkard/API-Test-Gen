"""
Reports and analytics endpoints.
"""
import re
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.db.database import get_db
from app.db.models import Project, TestSuite, TestExecution, ProjectConfig

router = APIRouter()


def _update_endpoint_stats(endpoint_stats: Dict[str, Any], result: Dict[str, Any]) -> None:
    """
    Update endpoint statistics with normalized endpoint path and test type tracking.
    
    Args:
        endpoint_stats: Dictionary to update with endpoint statistics
        result: Test execution result dictionary
    """
    endpoint = result.get('endpoint', 'unknown')
    method = result.get('method', 'unknown')
    test_type = result.get('test_type') or result.get('type', 'unknown')
    
    # Normalize endpoint path to group by base pattern
    normalized_endpoint = normalize_endpoint_path(endpoint)
    key = f"{method} {normalized_endpoint}"
    
    if key not in endpoint_stats:
        endpoint_stats[key] = {
            'endpoint': normalized_endpoint,  # Use normalized endpoint
            'method': method,
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'test_types': {}  # Track test types for this endpoint
        }
    
    endpoint_stats[key]['total'] += 1
    status = result.get('status', 'unknown')
    if status == 'passed':
        endpoint_stats[key]['passed'] += 1
    elif status == 'failed':
        endpoint_stats[key]['failed'] += 1
    else:
        endpoint_stats[key]['errors'] += 1
    
    # Track test types
    if test_type not in endpoint_stats[key]['test_types']:
        endpoint_stats[key]['test_types'][test_type] = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0
        }
    endpoint_stats[key]['test_types'][test_type]['total'] += 1
    if status == 'passed':
        endpoint_stats[key]['test_types'][test_type]['passed'] += 1
    elif status == 'failed':
        endpoint_stats[key]['test_types'][test_type]['failed'] += 1
    else:
        endpoint_stats[key]['test_types'][test_type]['errors'] += 1


def normalize_endpoint_path(endpoint: str) -> str:
    """
    Normalize endpoint path by replacing dynamic values with placeholders.
    
    Examples:
    - /user/testuser_x1rm0q -> /user/{username}
    - /user/a -> /user/{username}
    - /user/admin'; DROP TABLE users; -> /user/{username}
    - /pet/12345 -> /pet/{petId}
    - /store/order/67890 -> /store/order/{orderId}
    
    Args:
        endpoint: Endpoint path with actual values
        
    Returns:
        Normalized endpoint path with placeholders
    """
    if not endpoint or endpoint == 'unknown':
        return endpoint
    
    # Split path into segments
    parts = endpoint.split('/')
    normalized_parts = []
    
    # Common static path segments that should NOT be normalized
    # These are typically API version prefixes, common resource names, etc.
    common_static_segments = {
        'api', 'v1', 'v2', 'v3', 'api', 'rest', 'graphql',
        'health', 'status', 'docs', 'swagger', 'openapi'
    }
    
    for i, part in enumerate(parts):
        if not part:
            normalized_parts.append(part)
            continue
        
        # If it's a known static segment, keep it as-is
        if part.lower() in common_static_segments:
            normalized_parts.append(part)
            continue
        
        # Check if this looks like a dynamic value
        is_dynamic = False
        placeholder = '{id}'
        
        # Pattern 1: UUIDs
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if re.match(uuid_pattern, part, re.IGNORECASE):
            is_dynamic = True
            placeholder = '{id}'
        # Pattern 2: Numeric IDs
        elif re.match(r'^\d+$', part):
            is_dynamic = True
            placeholder = '{id}'
        # Pattern 3: Contains special characters (SQL injection, XSS, etc.) - definitely dynamic
        elif re.search(r'[<>;\'"`@#$%^&*()\[\]{}\\|]', part):
            is_dynamic = True
            # Try to infer placeholder based on parent path
            if i > 0 and parts[i-1].lower() in ['user', 'users']:
                placeholder = '{username}'
            else:
                placeholder = '{id}'
        # Pattern 4: Contains Unicode/non-ASCII characters - likely dynamic
        elif not part.isascii():
            is_dynamic = True
            if i > 0 and parts[i-1].lower() in ['user', 'users']:
                placeholder = '{username}'
            else:
                placeholder = '{id}'
        # Pattern 5: Single character or very short string after a resource - likely dynamic
        elif len(part) <= 3 and i > 0:
            # Check if previous segment is a known resource
            prev_segment = parts[i-1].lower()
            if prev_segment in ['user', 'users', 'pet', 'pets', 'order', 'orders']:
                is_dynamic = True
                if prev_segment in ['user', 'users']:
                    placeholder = '{username}'
                elif prev_segment in ['pet', 'pets']:
                    placeholder = '{petId}'
                elif prev_segment in ['order', 'orders']:
                    placeholder = '{orderId}'
                else:
                    placeholder = '{id}'
        # Pattern 6: Username-like patterns (testuser_xxx, user_xxx, etc.)
        elif re.match(r'^(test)?user[_\-]?[a-z0-9]+$', part, re.IGNORECASE):
            is_dynamic = True
            placeholder = '{username}'
        # Pattern 7: Long alphanumeric strings (likely IDs)
        elif len(part) > 10 and re.match(r'^[a-z0-9_\-]+$', part, re.IGNORECASE):
            is_dynamic = True
            placeholder = '{id}'
        # Pattern 8: If it's not a common static segment and doesn't look like a standard path,
        # and we're after a known resource path, treat as dynamic
        elif i > 0:
            prev_segment = parts[i-1].lower()
            # If previous segment is a known resource and current doesn't look like a static path
            if prev_segment in ['user', 'users', 'pet', 'pets', 'order', 'orders', 'store']:
                # If it doesn't match standard path patterns, it's likely dynamic
                if not re.match(r'^[a-z][a-z0-9\-_]*$', part, re.IGNORECASE):
                    is_dynamic = True
                    if prev_segment in ['user', 'users']:
                        placeholder = '{username}'
                    elif prev_segment in ['pet', 'pets']:
                        placeholder = '{petId}'
                    elif prev_segment in ['order', 'orders']:
                        placeholder = '{orderId}'
                    else:
                        placeholder = '{id}'
        
        if is_dynamic:
            normalized_parts.append(placeholder)
        else:
            normalized_parts.append(part)
    
    return '/'.join(normalized_parts)


@router.get("/")
def get_reports(
    project_id: Optional[UUID] = None,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive test execution reports.
    
    Args:
        project_id: Optional project ID to filter
        days: Number of days to include in report
        db: Database session
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Base query - include all executions, filter by date if completed
    query = db.query(TestExecution)
    
    # Filter by date if completed_at exists, otherwise include all
    query = query.filter(
        or_(
            TestExecution.completed_at.is_(None),
            TestExecution.completed_at >= start_date
        )
    )
    
    if project_id:
        # Get test suites for this project
        test_suites = db.query(TestSuite.id).filter(
            TestSuite.project_id == project_id
        ).subquery()
        query = query.filter(TestExecution.test_suite_id.in_(test_suites))
    
    executions = query.all()
    
    # Aggregate metrics
    total_executions = len(executions)
    total_tests = sum(
        exec.summary.get('total', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_passed = sum(
        exec.summary.get('passed', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_failed = sum(
        exec.summary.get('failed', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_errors = sum(
        exec.summary.get('errors', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    
    # Test type breakdown
    test_type_counts = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    test_type = result.get('test_type') or result.get('type', 'unknown')
                    test_type_counts[test_type] = test_type_counts.get(test_type, 0) + 1
    
    # Status breakdown
    status_counts = {
        'passed': total_passed,
        'failed': total_failed,
        'errors': total_errors
    }
    
    # Daily trends
    daily_stats = {}
    for exec in executions:
        if exec.completed_at:
            try:
                date_key = exec.completed_at.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        'date': date_key,
                        'executions': 0,
                        'tests': 0,
                        'passed': 0,
                        'failed': 0,
                        'errors': 0
                    }
                daily_stats[date_key]['executions'] += 1
                if exec.summary and isinstance(exec.summary, dict):
                    daily_stats[date_key]['tests'] += exec.summary.get('total', 0)
                    daily_stats[date_key]['passed'] += exec.summary.get('passed', 0)
                    daily_stats[date_key]['failed'] += exec.summary.get('failed', 0)
                    daily_stats[date_key]['errors'] += exec.summary.get('errors', 0)
            except Exception:
                continue
    
    # Security findings
    security_findings = []
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict) and result.get('security_finding'):
                    security_findings.append({
                        'test_name': result.get('test_name', 'Unknown'),
                        'endpoint': result.get('endpoint', 'Unknown'),
                        'method': result.get('method', 'Unknown'),
                        'error': result.get('error', ''),
                        'execution_id': str(exec.id),
                        'date': exec.completed_at.isoformat() if exec.completed_at else None
                    })
    
    # Endpoint performance - group by normalized endpoint and test type
    endpoint_stats = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    _update_endpoint_stats(endpoint_stats, result)
    
    # Calculate pass rates for each endpoint
    for key in endpoint_stats:
        endpoint_total = endpoint_stats[key]['total']
        endpoint_passed = endpoint_stats[key]['passed']
        endpoint_stats[key]['pass_rate'] = round((endpoint_passed / endpoint_total * 100) if endpoint_total > 0 else 0, 2)
    
    # Calculate pass rates
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    return {
        'summary': {
            'total_executions': total_executions,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_errors': total_errors,
            'pass_rate': round(pass_rate, 2),
            'period_days': days
        },
        'test_type_breakdown': test_type_counts,
        'status_breakdown': status_counts,
        'daily_trends': list(daily_stats.values()),
        'security_findings': security_findings[:50],  # Limit to 50
        'endpoint_performance': list(endpoint_stats.values())[:20],  # Top 20
        'time_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    }


@router.get("/project/{project_id}")
def get_project_report(
    project_id: UUID,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get report for a specific project."""
    return get_reports(project_id=project_id, days=days, db=db)


@router.get("/executions")
def get_execution_list(
    project_id: Optional[UUID] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get list of recent executions."""
    query = db.query(TestExecution).order_by(TestExecution.started_at.desc())
    
    if project_id:
        test_suites = db.query(TestSuite.id).filter(
            TestSuite.project_id == project_id
        ).subquery()
        query = query.filter(TestExecution.test_suite_id.in_(test_suites))
    
    executions = query.limit(limit).all()
    
    return [
        {
            'execution_id': str(exec.id),
            'test_suite_id': str(exec.test_suite_id),
            'status': exec.status,
            'summary': exec.summary,
            'started_at': exec.started_at.isoformat() if exec.started_at else None,
            'completed_at': exec.completed_at.isoformat() if exec.completed_at else None,
        }
        for exec in executions
    ]


@router.get("/last-run")
def get_last_run_report(
    project_id: Optional[UUID] = None,
    test_suite_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Get the last test execution report with detailed results."""
    query = db.query(TestExecution).order_by(TestExecution.started_at.desc())
    
    if test_suite_id:
        query = query.filter(TestExecution.test_suite_id == test_suite_id)
    elif project_id:
        test_suites = db.query(TestSuite.id).filter(
            TestSuite.project_id == project_id
        ).subquery()
        query = query.filter(TestExecution.test_suite_id.in_(test_suites))
    
    last_execution = query.first()
    
    if not last_execution:
        raise HTTPException(status_code=404, detail="No executions found")
    
    # Get test suite info
    test_suite = db.query(TestSuite).filter(TestSuite.id == last_execution.test_suite_id).first()
    
    # Aggregate metrics from this single execution
    results = last_execution.results or []
    summary = last_execution.summary or {}
    
    # Test type breakdown
    test_type_counts = {}
    for result in results:
        if isinstance(result, dict):
            test_type = result.get('test_type') or result.get('type', 'unknown')
            test_type_counts[test_type] = test_type_counts.get(test_type, 0) + 1
    
    # Status breakdown
    status_counts = {
        'passed': summary.get('passed', 0),
        'failed': summary.get('failed', 0),
        'errors': summary.get('errors', 0)
    }
    
    # Security findings
    security_findings = []
    for result in results:
        if isinstance(result, dict) and result.get('security_finding'):
            security_findings.append({
                'test_name': result.get('test_name', 'Unknown'),
                'endpoint': result.get('endpoint', 'Unknown'),
                'method': result.get('method', 'Unknown'),
                'error': result.get('error', ''),
                'execution_id': str(last_execution.id),
                'date': last_execution.completed_at.isoformat() if last_execution.completed_at else None
            })
    
    # Endpoint performance - group by normalized endpoint and test type
    endpoint_stats = {}
    for result in results:
        if isinstance(result, dict):
            _update_endpoint_stats(endpoint_stats, result)
    
    # Calculate pass rates for each endpoint
    for key in endpoint_stats:
        endpoint_total = endpoint_stats[key]['total']
        endpoint_passed = endpoint_stats[key]['passed']
        endpoint_stats[key]['pass_rate'] = round((endpoint_passed / endpoint_total * 100) if endpoint_total > 0 else 0, 2)
    
    total_tests = summary.get('total', len(results))
    total_passed = summary.get('passed', 0)
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    return {
        'execution_id': str(last_execution.id),
        'test_suite_id': str(last_execution.test_suite_id),
        'test_suite_name': test_suite.name if test_suite else 'Unknown',
        'status': last_execution.status,
        'started_at': last_execution.started_at.isoformat() if last_execution.started_at else None,
        'completed_at': last_execution.completed_at.isoformat() if last_execution.completed_at else None,
        'summary': {
            'total_executions': 1,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': summary.get('failed', 0),
            'total_errors': summary.get('errors', 0),
            'pass_rate': round(pass_rate, 2),
            'period_days': 0  # Single execution
        },
        'test_type_breakdown': test_type_counts,
        'status_breakdown': status_counts,
        'security_findings': security_findings,
        'endpoint_performance': list(endpoint_stats.values()),
        'results': results,
        'time_range': {
            'start': last_execution.started_at.isoformat() if last_execution.started_at else None,
            'end': last_execution.completed_at.isoformat() if last_execution.completed_at else None
        }
    }


@router.get("/test-suite/{test_suite_id}")
def get_test_suite_report(
    test_suite_id: UUID,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get report for a specific test suite."""
    test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
    if not test_suite:
        raise HTTPException(status_code=404, detail="Test suite not found")
    
    # Get project info
    project = db.query(Project).filter(Project.id == test_suite.project_id).first()
    
    # Get executions for this test suite
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    executions = db.query(TestExecution).filter(
        TestExecution.test_suite_id == test_suite_id
    ).filter(
        or_(
            TestExecution.completed_at.is_(None),
            TestExecution.completed_at >= start_date
        )
    ).all()
    
    # Aggregate metrics (same logic as project report)
    total_executions = len(executions)
    total_tests = sum(
        exec.summary.get('total', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_passed = sum(
        exec.summary.get('passed', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_failed = sum(
        exec.summary.get('failed', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    total_errors = sum(
        exec.summary.get('errors', 0) if exec.summary and isinstance(exec.summary, dict) else 0 
        for exec in executions
    )
    
    # Test type breakdown
    test_type_counts = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    test_type = result.get('test_type') or result.get('type', 'unknown')
                    test_type_counts[test_type] = test_type_counts.get(test_type, 0) + 1
    
    # Status breakdown
    status_counts = {
        'passed': total_passed,
        'failed': total_failed,
        'errors': total_errors
    }
    
    # Daily trends
    daily_stats = {}
    for exec in executions:
        if exec.completed_at:
            try:
                date_key = exec.completed_at.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        'date': date_key,
                        'executions': 0,
                        'tests': 0,
                        'passed': 0,
                        'failed': 0,
                        'errors': 0
                    }
                daily_stats[date_key]['executions'] += 1
                if exec.summary and isinstance(exec.summary, dict):
                    daily_stats[date_key]['tests'] += exec.summary.get('total', 0)
                    daily_stats[date_key]['passed'] += exec.summary.get('passed', 0)
                    daily_stats[date_key]['failed'] += exec.summary.get('failed', 0)
                    daily_stats[date_key]['errors'] += exec.summary.get('errors', 0)
            except Exception:
                continue
    
    # Security findings
    security_findings = []
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict) and result.get('security_finding'):
                    security_findings.append({
                        'test_name': result.get('test_name', 'Unknown'),
                        'endpoint': result.get('endpoint', 'Unknown'),
                        'method': result.get('method', 'Unknown'),
                        'error': result.get('error', ''),
                        'execution_id': str(exec.id),
                        'date': exec.completed_at.isoformat() if exec.completed_at else None
                    })
    
    # Endpoint performance - group by normalized endpoint and test type
    endpoint_stats = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    _update_endpoint_stats(endpoint_stats, result)
    
    # Calculate pass rates for each endpoint
    for key in endpoint_stats:
        endpoint_total = endpoint_stats[key]['total']
        endpoint_passed = endpoint_stats[key]['passed']
        endpoint_stats[key]['pass_rate'] = round((endpoint_passed / endpoint_total * 100) if endpoint_total > 0 else 0, 2)
    
    # Calculate overall pass rate
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    return {
        'test_suite_id': str(test_suite.id),
        'test_suite_name': test_suite.name,
        'project_id': str(test_suite.project_id),
        'project_name': project.name if project else 'Unknown',
        'summary': {
            'total_executions': total_executions,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'total_errors': total_errors,
            'pass_rate': round(pass_rate, 2),
            'period_days': days
        },
        'test_type_breakdown': test_type_counts,
        'status_breakdown': status_counts,
        'daily_trends': list(daily_stats.values()),
        'security_findings': security_findings[:50],
        'endpoint_performance': list(endpoint_stats.values())[:20],
        'time_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    }


@router.get("/projects")
def get_projects_with_test_suites(
    db: Session = Depends(get_db)
):
    """Get all projects with their test suites for global reports."""
    projects = db.query(Project).all()
    
    result = []
    for project in projects:
        test_suites = db.query(TestSuite).filter(
            TestSuite.project_id == project.id
        ).all()
        
        # Get execution counts for each test suite
        test_suites_data = []
        for suite in test_suites:
            execution_count = db.query(TestExecution).filter(
                TestExecution.test_suite_id == suite.id
            ).count()
            
            # Get latest execution
            latest_execution = db.query(TestExecution).filter(
                TestExecution.test_suite_id == suite.id
            ).order_by(TestExecution.started_at.desc()).first()
            
            test_suites_data.append({
                'id': str(suite.id),
                'name': suite.name,
                'test_count': len(suite.test_cases) if suite.test_cases else 0,
                'execution_count': execution_count,
                'latest_execution': {
                    'id': str(latest_execution.id) if latest_execution else None,
                    'status': latest_execution.status if latest_execution else None,
                    'started_at': latest_execution.started_at.isoformat() if latest_execution and latest_execution.started_at else None,
                    'completed_at': latest_execution.completed_at.isoformat() if latest_execution and latest_execution.completed_at else None,
                } if latest_execution else None
            })
        
        result.append({
            'id': str(project.id),
            'name': project.name,
            'description': project.description,
            'test_suites': test_suites_data
        })
    
    return result


@router.get("/endpoint/{method}/{endpoint_path:path}/test-cases")
def get_endpoint_test_cases(
    method: str,
    endpoint_path: str,
    project_id: Optional[UUID] = None,
    test_suite_id: Optional[UUID] = None,
    execution_id: Optional[UUID] = None,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get test cases for a specific endpoint.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint_path: Endpoint path (e.g., /api/users/{id})
        project_id: Optional project ID to filter
        test_suite_id: Optional test suite ID to filter
        execution_id: Optional execution ID to get results from specific execution
        days: Number of days to look back (if execution_id not provided)
        db: Database session
    """
    # Normalize endpoint path (remove leading slash if present, add it back)
    if not endpoint_path.startswith('/'):
        endpoint_path = '/' + endpoint_path
    
    # Build query for test executions
    if execution_id:
        # Get specific execution
        executions = db.query(TestExecution).filter(TestExecution.id == execution_id).all()
    else:
        # Get recent executions
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = db.query(TestExecution).filter(
            or_(
                TestExecution.completed_at.is_(None),
                TestExecution.completed_at >= start_date
            )
        )
        
        if test_suite_id:
            query = query.filter(TestExecution.test_suite_id == test_suite_id)
        elif project_id:
            test_suites = db.query(TestSuite.id).filter(
                TestSuite.project_id == project_id
            ).subquery()
            query = query.filter(TestExecution.test_suite_id.in_(test_suites))
        
        executions = query.order_by(TestExecution.started_at.desc()).limit(10).all()
    
    # Collect test cases for this endpoint
    test_cases = []
    seen_test_names = set()  # To avoid duplicates
    
    for execution in executions:
        if not execution.results or not isinstance(execution.results, list):
            continue
        
        for result in execution.results:
            if not isinstance(result, dict):
                continue
            
            # Match endpoint and method
            result_endpoint = result.get('endpoint', '')
            result_method = result.get('method', '').upper()
            
            # Normalize paths for comparison (handle path parameters)
            normalized_result_endpoint = normalize_endpoint_path(result_endpoint)
            if result_method == method.upper() and normalized_result_endpoint == endpoint_path:
                test_name = result.get('test_name', result.get('name', 'Unknown Test'))
                
                # Create unique key to avoid duplicates
                test_key = f"{test_name}_{result.get('type', 'unknown')}"
                if test_key in seen_test_names:
                    continue
                seen_test_names.add(test_key)
                
                # Extract test case details
                test_case = {
                    'test_name': test_name,
                    'test_type': result.get('test_type', result.get('type', 'unknown')),
                    'status': result.get('status', 'unknown'),
                    'endpoint': result_endpoint,
                    'method': result_method,
                    'request': {
                        'url': result.get('url', ''),
                        'method': result_method,
                        'headers': result.get('request_headers', result.get('headers', {})),
                        'payload': result.get('payload', result.get('request_body', {})),
                        'query_params': result.get('query_params', {}),
                    },
                    'response': {
                        'status_code': result.get('status_code', result.get('response_status', 0)),
                        'headers': result.get('response_headers', {}),
                        'body': result.get('response_body', result.get('response', '')),
                    },
                    'expected': {
                        'status': result.get('expected_status', [200]),
                        'assertions': result.get('assertions', []),
                    },
                    'error': result.get('error', ''),
                    'execution_id': str(execution.id),
                    'executed_at': execution.completed_at.isoformat() if execution.completed_at else execution.started_at.isoformat() if execution.started_at else None,
                }
                
                # Add trace if available (for multi-step tests)
                if result.get('trace'):
                    test_case['trace'] = result.get('trace')
                
                test_cases.append(test_case)
    
    # Get test suite info if available
    test_suite_name = None
    if test_suite_id:
        test_suite = db.query(TestSuite).filter(TestSuite.id == test_suite_id).first()
        if test_suite:
            test_suite_name = test_suite.name
    
    # Group test cases by test type
    test_cases_by_type = {}
    for test_case in test_cases:
        test_type = test_case.get('test_type', 'unknown')
        if test_type not in test_cases_by_type:
            test_cases_by_type[test_type] = []
        test_cases_by_type[test_type].append(test_case)
    
    return {
        'endpoint': endpoint_path,
        'method': method.upper(),
        'test_cases': test_cases,
        'test_cases_by_type': test_cases_by_type,  # Grouped by type
        'total_count': len(test_cases),
        'test_suite_id': str(test_suite_id) if test_suite_id else None,
        'test_suite_name': test_suite_name,
    }

