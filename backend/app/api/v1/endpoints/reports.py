"""
Reports and analytics endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.db.database import get_db
from app.db.models import Project, TestSuite, TestExecution, ProjectConfig

router = APIRouter()


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
    
    # Endpoint performance
    endpoint_stats = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    endpoint = result.get('endpoint', 'unknown')
                    method = result.get('method', 'unknown')
                    key = f"{method} {endpoint}"
                    
                    if key not in endpoint_stats:
                        endpoint_stats[key] = {
                            'endpoint': endpoint,
                            'method': method,
                            'total': 0,
                            'passed': 0,
                            'failed': 0,
                            'errors': 0
                        }
                    
                    endpoint_stats[key]['total'] += 1
                    status = result.get('status', 'unknown')
                    if status == 'passed':
                        endpoint_stats[key]['passed'] += 1
                    elif status == 'failed':
                        endpoint_stats[key]['failed'] += 1
                    else:
                        endpoint_stats[key]['errors'] += 1
    
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
    
    # Endpoint performance
    endpoint_stats = {}
    for result in results:
        if isinstance(result, dict):
            endpoint = result.get('endpoint', 'unknown')
            method = result.get('method', 'unknown')
            key = f"{method} {endpoint}"
            
            if key not in endpoint_stats:
                endpoint_stats[key] = {
                    'endpoint': endpoint,
                    'method': method,
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'errors': 0
                }
            
            endpoint_stats[key]['total'] += 1
            status = result.get('status', 'unknown')
            if status == 'passed':
                endpoint_stats[key]['passed'] += 1
            elif status == 'failed':
                endpoint_stats[key]['failed'] += 1
            else:
                endpoint_stats[key]['errors'] += 1
    
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
    
    # Endpoint performance
    endpoint_stats = {}
    for exec in executions:
        if exec.results and isinstance(exec.results, list):
            for result in exec.results:
                if isinstance(result, dict):
                    endpoint = result.get('endpoint', 'unknown')
                    method = result.get('method', 'unknown')
                    key = f"{method} {endpoint}"
                    
                    if key not in endpoint_stats:
                        endpoint_stats[key] = {
                            'endpoint': endpoint,
                            'method': method,
                            'total': 0,
                            'passed': 0,
                            'failed': 0,
                            'errors': 0
                        }
                    
                    endpoint_stats[key]['total'] += 1
                    status = result.get('status', 'unknown')
                    if status == 'passed':
                        endpoint_stats[key]['passed'] += 1
                    elif status == 'failed':
                        endpoint_stats[key]['failed'] += 1
                    else:
                        endpoint_stats[key]['errors'] += 1
    
    # Calculate pass rates
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

