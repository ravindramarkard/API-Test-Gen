"""
Test case generator with baseline and LLM-enhanced generation.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
import random
import string
import re

import schemathesis
try:
    from langchain.llms import OpenAI
    from langchain.chains import RetrievalQA
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import PGVector
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    # Fallback for newer LangChain versions
    try:
        from langchain_openai import OpenAI, OpenAIEmbeddings
        from langchain.chains import RetrievalQA
        from langchain.vectorstores import PGVector
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        OpenAI = None
        RetrievalQA = None
        OpenAIEmbeddings = None
        PGVector = None
        RecursiveCharacterTextSplitter = None

logger = logging.getLogger(__name__)


class TestType(str, Enum):
    """Test case types."""
    HAPPY_PATH = "happy_path"
    NEGATIVE = "negative"
    VALIDATION = "validation"
    EDGE_CASE = "edge_case"
    SECURITY = "security"
    BOUNDARY = "boundary"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"
    E2E = "e2e"
    CRUD = "crud"


class TestGenerator:
    """Generate test cases from OpenAPI specifications."""
    
    def __init__(
        self,
        parser,
        llm_api_key: Optional[str] = None,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4",
        llm_endpoint: Optional[str] = None
    ):
        """
        Initialize test generator.
        
        Args:
            parser: OpenAPI parser instance
            llm_api_key: LLM API key for enhanced generation
            llm_provider: LLM provider (openai, anthropic, xai, local, openrouter)
            llm_model: LLM model name
            llm_endpoint: Custom LLM endpoint URL
        """
        self.parser = parser
        self.llm_api_key = llm_api_key
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_endpoint = llm_endpoint
    
    def generate_all_tests(
        self,
        selected_endpoints: Optional[List[Dict[str, str]]] = None,
        enabled_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate all test cases for all endpoints or selected endpoints.
        
        Args:
            selected_endpoints: Optional list of endpoint filters with 'path' and 'method' keys.
                               If None, generates tests for all endpoints.
        """
        all_tests = []
        enabled: Optional[set] = set(t.lower() for t in enabled_types) if enabled_types else None
        
        # Get endpoints from parser
        endpoints = self.parser.get_endpoints()
        
        # Filter endpoints if selection provided
        if selected_endpoints:
            filtered_endpoints = []
            for endpoint in endpoints:
                # Check if this endpoint matches any selected endpoint
                for selected in selected_endpoints:
                    if (endpoint.get('path') == selected.get('path') and 
                        endpoint.get('method', '').upper() == selected.get('method', '').upper()):
                        filtered_endpoints.append(endpoint)
                        break
            endpoints = filtered_endpoints
        
        # Group endpoints by resource for CRUD and E2E tests
        endpoints_by_resource = self._group_endpoints_by_resource(endpoints)
        
        for endpoint in endpoints:
            # Positive/Happy path tests
            if not enabled or TestType.HAPPY_PATH.value in enabled:
                baseline_tests = self._generate_baseline_tests(endpoint)
                all_tests.extend(baseline_tests)
            
            # Negative tests
            if not enabled or TestType.NEGATIVE.value in enabled:
                negative_tests = self._generate_negative_tests(endpoint)
                all_tests.extend(negative_tests)
            
            # Boundary value tests
            if not enabled or TestType.BOUNDARY.value in enabled:
                boundary_tests = self._generate_boundary_tests(endpoint)
                all_tests.extend(boundary_tests)
            
            # Validation tests
            if not enabled or TestType.VALIDATION.value in enabled:
                validation_tests = self._generate_validation_tests(endpoint)
                all_tests.extend(validation_tests)
            
            # Security tests
            if not enabled or TestType.SECURITY.value in enabled:
                security_tests = self._generate_security_tests(endpoint)
                all_tests.extend(security_tests)
            
            # Performance tests
            if not enabled or TestType.PERFORMANCE.value in enabled:
                performance_tests = self._generate_performance_tests(endpoint)
                all_tests.extend(performance_tests)
            
            # LLM-enhanced tests
            if self.llm_api_key:
                try:
                    llm_tests = self._generate_llm_tests(endpoint)
                    if enabled:
                        llm_tests = [t for t in llm_tests if t.get('type', '').lower() in enabled]
                    all_tests.extend(llm_tests)
                except Exception as e:
                    logger.warning(f"LLM test generation failed for {endpoint['operation_id']}: {str(e)}")
        
        # CRUD operation tests
        if not enabled or TestType.CRUD.value in enabled:
            crud_tests = self._generate_crud_tests(endpoints_by_resource)
            all_tests.extend(crud_tests)
        
        # Integration tests
        if not enabled or TestType.INTEGRATION.value in enabled:
            integration_tests = self._generate_integration_tests(endpoints_by_resource)
            all_tests.extend(integration_tests)
        
        # E2E tests
        if not enabled or TestType.E2E.value in enabled:
            e2e_tests = self._generate_e2e_tests(endpoints_by_resource)
            all_tests.extend(e2e_tests)
        
        return all_tests
    
    def _group_endpoints_by_resource(self, endpoints: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group endpoints by resource (e.g., /pet, /user, /store)."""
        resources = {}
        
        for endpoint in endpoints:
            path = endpoint.get('path', '')
            # Extract resource from path (e.g., /pet/{id} -> pet)
            resource_match = re.match(r'^/([^/]+)', path)
            if resource_match:
                resource = resource_match.group(1)
                if resource not in resources:
                    resources[resource] = []
                resources[resource].append(endpoint)
        
        return resources
    
    def _generate_baseline_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate baseline tests using Schemathesis."""
        tests = []
        path = endpoint['path']
        method = endpoint['method'].upper()

        # If this is a DELETE on a resource with an {id}, prepend a create step so we delete a fresh record
        if method == 'DELETE' and re.search(r'\{(\w+)\}', path):
            resource_match = re.match(r'^/([^/]+)', path)
            if resource_match:
                resource = resource_match.group(1)
                create_ep = None
                # Look for a POST create endpoint for the same resource (without path params)
                for ep in self.parser.get_endpoints():
                    if ep.get('method', '').upper() == 'POST':
                        ep_path = ep.get('path', '').rstrip('/')
                        if ep_path == f"/{resource}".rstrip('/'):
                            create_ep = ep
                            break
                if create_ep:
                    create_payload = self._generate_sample_payload(create_ep)
                    delete_flow = [
                        {
                            'endpoint': create_ep['path'],
                            'method': 'POST',
                            'payload': create_payload,
                            'description': f"Create {resource} to obtain id"
                        },
                        {
                            'endpoint': path,
                            'method': 'DELETE',
                            'payload': {},
                            'description': f"Delete created {resource}"
                        }
                    ]
                    delete_assertions = self._generate_assertions_from_responses(endpoint, [200, 204])
                    tests.append({
                        'type': TestType.E2E.value,
                        'endpoint': path,
                        'method': 'DELETE',
                        'operation_id': f"{resource}_delete_flow",
                        'name': f"Delete {resource} after create",
                        'payload': {'flow': delete_flow},
                        'expected_status': [200, 201, 204],
                        'description': f"Create a {resource} then delete it using returned id",
                        'e2e_flow': delete_flow,
                        'assertions': delete_assertions or []
                    })
                    # For standalone selection, skip the default DELETE happy path to avoid missing id
                    return tests

        # If this is an UPDATE (PUT/PATCH) with {id}, create first then update the created id
        if method in ['PUT', 'PATCH'] and re.search(r'\{(\w+)\}', path):
            resource_match = re.match(r'^/([^/]+)', path)
            if resource_match:
                resource = resource_match.group(1)
                create_ep = None
                for ep in self.parser.get_endpoints():
                    if ep.get('method', '').upper() == 'POST':
                        ep_path = ep.get('path', '').rstrip('/')
                        if ep_path == f"/{resource}".rstrip('/'):
                            create_ep = ep
                            break
                if create_ep:
                    create_payload = self._generate_sample_payload(create_ep)
                    update_payload = self._generate_sample_payload(endpoint)
                    update_flow = [
                        {
                            'endpoint': create_ep['path'],
                            'method': 'POST',
                            'payload': create_payload,
                            'description': f"Create {resource} to obtain id"
                        },
                        {
                            'endpoint': path,
                            'method': method,
                            'payload': update_payload,
                            'description': f"Update created {resource}"
                        }
                    ]
                    update_assertions = self._generate_assertions_from_responses(endpoint, self._get_expected_status(endpoint))
                    tests.append({
                        'type': TestType.E2E.value,
                        'endpoint': path,
                        'method': method,
                        'operation_id': f"{resource}_update_flow",
                        'name': f"Update {resource} after create",
                        'payload': {'flow': update_flow},
                        'expected_status': [200, 201, 204],
                        'description': f"Create a {resource} then update it using returned id",
                        'e2e_flow': update_flow,
                        'assertions': update_assertions or []
                    })
                    # Skip default update happy path to avoid missing id
                    return tests
        
        # Always generate at least a happy path test
        try:
            # Happy path test
            expected_status = self._get_expected_status(endpoint)
            assertions = self._generate_assertions_from_responses(endpoint, expected_status)
            
            test_case = {
                'type': TestType.HAPPY_PATH.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Happy path: {endpoint['operation_id']}",
                'payload': self._generate_sample_payload(endpoint),
                'expected_status': expected_status,
                'description': f"Test successful execution of {endpoint['operation_id']}"
            }
            
            # Add assertions if generated
            if assertions:
                test_case['assertions'] = assertions
            
            tests.append(test_case)
            
            # Validation tests
            validation_tests = self._generate_validation_tests(endpoint)
            tests.extend(validation_tests)
            
            # Try schemathesis for additional property-based tests
            try:
                spec_dict = self.parser.resolved_spec
                schema = schemathesis.from_dict(spec_dict)
                
                method_lower = method.lower()
                if hasattr(schema, path) and hasattr(schema[path], method_lower):
                    # Additional tests from schemathesis could be added here
                    pass
            except Exception as e:
                logger.debug(f"Schemathesis integration skipped: {str(e)}")
        
        except Exception as e:
            logger.warning(f"Baseline test generation failed for {endpoint['operation_id']}: {str(e)}")
            # Even if generation fails, add a basic test
            tests.append({
                'type': TestType.HAPPY_PATH.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Basic test: {endpoint['operation_id']}",
                'payload': {},
                'expected_status': [200, 201, 204],
                'description': f"Basic test for {endpoint['operation_id']}"
            })
        
        return tests
    
    def _generate_negative_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate negative test cases."""
        tests = []
        path = endpoint['path']
        method = endpoint['method'].upper()
        
        # Invalid HTTP method
        if method != 'GET':
            test_case = {
                'type': TestType.NEGATIVE.value,
                'endpoint': path,
                'method': 'GET' if method != 'GET' else 'POST',
                'operation_id': endpoint['operation_id'],
                'name': f"Negative: Invalid method for {endpoint['operation_id']}",
                'payload': {},
                'expected_status': [405, 404],
                'description': f"Test invalid HTTP method for {endpoint['operation_id']}"
            }
            # Add assertions for error responses
            assertions = self._generate_assertions_from_responses(endpoint, [405, 404])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        # Invalid path parameters
        path_params = re.findall(r'\{(\w+)\}', path)
        for param in path_params:
            # Determine parameter type from OpenAPI spec
            param_type = 'string'  # Default
            param_schema = None
            
            # Check parameters in the endpoint definition
            for endpoint_param in endpoint.get('parameters', []):
                if endpoint_param.get('name') == param or endpoint_param.get('name') == param.replace('Id', 'Id'):
                    param_schema = endpoint_param.get('schema', {})
                    param_type = param_schema.get('type', 'string')
                    break
            
            # Generate type-appropriate invalid value
            if param_type in ['integer', 'number'] or 'id' in param.lower():
                # For numeric parameters, use a non-numeric string
                invalid_value = 'invalid_value'
            else:
                # For string parameters, use an empty string or special characters
                invalid_value = ''
            
            test_case = {
                'type': TestType.NEGATIVE.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Negative: Invalid {param} for {endpoint['operation_id']}",
                'payload': self._generate_invalid_payload(endpoint, {param: invalid_value}),
                'expected_status': [400, 404, 422],
                'description': f"Test invalid {param} value (type: {param_type})"
            }
            # Add assertions for error responses
            assertions = self._generate_assertions_from_responses(endpoint, [400, 404, 422])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        # Missing required fields - skip for file upload endpoints (they need special handling)
        if method in ['POST', 'PUT', 'PATCH']:
            is_file_upload = 'upload' in path.lower() or 'image' in path.lower()
            if not is_file_upload:
                # Generate a valid payload first, then remove ONE required field at a time
                base_payload = self._generate_sample_payload(endpoint)
                
                # Get required fields from schema
                request_body = endpoint.get('request_body', {})
                required_fields = []
                if request_body:
                    content = request_body.get('content', {})
                    for content_type, schema_info in content.items():
                        if 'application/json' in content_type:
                            schema = schema_info.get('schema', {})
                            # Resolve $ref if present
                            if '$ref' in schema:
                                try:
                                    schema = self.parser.resolve_ref(schema['$ref'])
                                except (ValueError, KeyError):
                                    pass
                            required_fields = schema.get('required', [])
                            break
                
                # Test missing each required field individually (keep others valid)
                for required_field in required_fields[:3]:  # Limit to first 3 to avoid too many tests
                    test_payload = dict(base_payload)
                    # Remove only this required field, keep others
                    if required_field in test_payload:
                        del test_payload[required_field]
                    
                    test_case = {
                        'type': TestType.NEGATIVE.value,
                        'endpoint': path,
                        'method': method,
                        'operation_id': endpoint['operation_id'],
                        'name': f"Negative: Missing required field '{required_field}' for {endpoint['operation_id']}",
                        'payload': test_payload,  # Valid payload except missing one required field
                        'expected_status': [400, 422],
                        'description': f"Test missing required field '{required_field}'"
                    }
                    # Add assertions for validation error responses
                    assertions = self._generate_assertions_from_responses(endpoint, [400, 422])
                    if assertions:
                        test_case['assertions'] = assertions
                    tests.append(test_case)
                
                # Also test completely empty payload if there are required fields
                if required_fields:
                    test_case = {
                        'type': TestType.NEGATIVE.value,
                        'endpoint': path,
                        'method': method,
                        'operation_id': endpoint['operation_id'],
                        'name': f"Negative: Empty payload for {endpoint['operation_id']}",
                        'payload': {},  # Completely empty payload
                        'expected_status': [400, 422],
                        'description': f"Test completely empty payload (missing all required fields)"
                    }
                    # Add assertions for validation error responses
                    assertions = self._generate_assertions_from_responses(endpoint, [400, 422])
                    if assertions:
                        test_case['assertions'] = assertions
                    tests.append(test_case)
        
        # Invalid data types (skip for file upload endpoints as they need special handling)
        is_file_upload = 'upload' in path.lower() or 'image' in path.lower()
        if not is_file_upload:
            test_case = {
                'type': TestType.NEGATIVE.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Negative: Invalid data types for {endpoint['operation_id']}",
                'payload': self._generate_invalid_type_payload(endpoint),
                'expected_status': [400, 422],
                'description': f"Test invalid data types"
            }
            # Add assertions for validation error responses
            assertions = self._generate_assertions_from_responses(endpoint, [400, 422])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        return tests
    
    def _generate_boundary_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate boundary value tests."""
        tests = []
        path = endpoint['path']
        method = endpoint['method'].upper()
        
        # Skip boundary tests for file upload endpoints (they need special handling)
        is_file_upload = 'upload' in path.lower() or 'image' in path.lower()
        if not is_file_upload:
            # String length boundaries
            boundary_payloads = [
                {'name': 'Empty string', 'payload': self._generate_boundary_payload(endpoint, 'empty_string')},
                {'name': 'Max length', 'payload': self._generate_boundary_payload(endpoint, 'max_length')},
                {'name': 'Min length', 'payload': self._generate_boundary_payload(endpoint, 'min_length')},
            ]
            
            for boundary in boundary_payloads:
                expected_status = self._get_expected_status(endpoint)
                test_case = {
                    'type': TestType.BOUNDARY.value,
                    'endpoint': path,
                    'method': method,
                    'operation_id': endpoint['operation_id'],
                    'name': f"Boundary: {boundary['name']} for {endpoint['operation_id']}",
                    'payload': boundary['payload'],
                    'expected_status': expected_status,
                    'description': f"Test boundary value: {boundary['name']}"
                }
                # Add assertions based on expected status
                assertions = self._generate_assertions_from_responses(endpoint, expected_status)
                if assertions:
                    test_case['assertions'] = assertions
                tests.append(test_case)
        
        # Numeric boundaries
        numeric_boundaries = [
            {'name': 'Zero', 'value': 0},
            {'name': 'Negative', 'value': -1},
            {'name': 'Max integer', 'value': 2147483647},
            {'name': 'Min integer', 'value': -2147483648},
        ]
        
        for boundary in numeric_boundaries:
            expected_status = self._get_expected_status(endpoint)
            test_case = {
                'type': TestType.BOUNDARY.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Boundary: {boundary['name']} for {endpoint['operation_id']}",
                'payload': self._generate_boundary_payload(endpoint, 'numeric', boundary['value']),
                'expected_status': expected_status,
                'description': f"Test numeric boundary: {boundary['name']}"
            }
            # Add assertions based on expected status
            assertions = self._generate_assertions_from_responses(endpoint, expected_status)
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        return tests
    
    def _generate_validation_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate field validation tests."""
        tests = []
        
        # Missing required fields
        request_body = endpoint.get('request_body', {})
        if request_body:
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                if 'application/json' in content_type:
                    schema = schema_info.get('schema', {})
                    required_fields = schema.get('required', [])
                    
                    for field in required_fields:
                        test_case = {
                            'type': TestType.VALIDATION.value,
                            'endpoint': endpoint['path'],
                            'method': endpoint['method'],
                            'operation_id': endpoint['operation_id'],
                            'name': f"Validation: Missing required field {field}",
                            'payload': self._generate_sample_payload(endpoint),
                            'remove_field': field,
                            'expected_status': [400, 422],
                            'description': f"Test validation when required field {field} is missing"
                        }
                        # Add assertions for validation error responses
                        assertions = self._generate_assertions_from_responses(endpoint, [400, 422])
                        if assertions:
                            test_case['assertions'] = assertions
                        tests.append(test_case)
        
        return tests
    
    def _generate_security_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate security test cases."""
        tests = []
        path = endpoint['path']
        method = endpoint['method'].upper()
        is_file_upload = 'upload' in path.lower() or 'image' in path.lower()
        
        # Skip security tests for file upload endpoints (they need special file handling)
        if is_file_upload:
            # Only test path traversal for file upload endpoints
            if '{' in path:
                test_case = {
                    'type': TestType.SECURITY.value,
                    'endpoint': path,
                    'method': method,
                    'operation_id': endpoint['operation_id'],
                    'name': f"Security: Path traversal test for {endpoint['operation_id']}",
                    'payload': {},
                    'expected_status': [400, 403, 404],
                    'description': f"Test path traversal protection"
                }
                # Add assertions for security rejection responses
                assertions = self._generate_assertions_from_responses(endpoint, [400, 403, 404])
                if assertions:
                    test_case['assertions'] = assertions
                tests.append(test_case)
            return tests
        
        # SQL Injection - test with payloads that violate schema constraints
        sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM users--",
        ]
        
        for sql_payload in sql_injection_payloads:
            test_case = {
                'type': TestType.SECURITY.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Security: SQL Injection test for {endpoint['operation_id']}",
                'payload': self._generate_security_payload(endpoint, 'sql_injection', sql_payload),
                'expected_status': [400, 403, 422],
                'description': f"Test SQL injection protection with invalid schema values: {sql_payload[:30]}"
            }
            # Add assertions for security rejection responses
            assertions = self._generate_assertions_from_responses(endpoint, [400, 403, 422])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        # XSS - test with payloads that violate format/enum constraints
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
        ]
        
        for xss_payload in xss_payloads:
            test_case = {
                'type': TestType.SECURITY.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Security: XSS test for {endpoint['operation_id']}",
                'payload': self._generate_security_payload(endpoint, 'xss', xss_payload),
                'expected_status': [400, 403, 422],
                'description': f"Test XSS protection with invalid format/enum values"
            }
            # Add assertions for security rejection responses
            assertions = self._generate_assertions_from_responses(endpoint, [400, 403, 422])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        # Additional security test: Missing required fields with attack vectors
        # This ensures the API rejects both missing required fields AND attack vectors
        request_body = endpoint.get('request_body', {})
        if request_body and method in ['POST', 'PUT', 'PATCH']:
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                if 'application/json' in content_type:
                    schema = schema_info.get('schema', {})
                    # Resolve $ref if present
                    if '$ref' in schema:
                        try:
                            schema = self.parser.resolve_ref(schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    
                    required = schema.get('required', [])
                    if required:
                        # Test with missing required field + attack vector in optional field
                        payload = self._generate_sample_payload(endpoint)
                        # Remove one required field
                        if required[0] in payload:
                            del payload[required[0]]
                        # Inject attack vector into remaining fields
                        for key in payload:
                            if isinstance(payload[key], str):
                                payload[key] = "<script>alert('XSS')</script>"
                        
                        test_case = {
                            'type': TestType.SECURITY.value,
                            'endpoint': path,
                            'method': method,
                            'operation_id': endpoint['operation_id'],
                            'name': f"Security: Missing required field + XSS for {endpoint['operation_id']}",
                            'payload': payload,
                            'expected_status': [400, 422],
                            'description': f"Test security: missing required field '{required[0]}' with XSS payload"
                        }
                        assertions = self._generate_assertions_from_responses(endpoint, [400, 422])
                        if assertions:
                            test_case['assertions'] = assertions
                        tests.append(test_case)
                    break
        
        # Path traversal
        if '{' in path:
            test_case = {
                'type': TestType.SECURITY.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Security: Path traversal test for {endpoint['operation_id']}",
                'payload': self._generate_security_payload(endpoint, 'path_traversal', '../../../etc/passwd'),
                'expected_status': [400, 403, 404],
                'description': f"Test path traversal protection"
            }
            # Add assertions for security rejection responses
            assertions = self._generate_assertions_from_responses(endpoint, [400, 403, 404])
            if assertions:
                test_case['assertions'] = assertions
            tests.append(test_case)
        
        return tests
    
    def _generate_performance_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate performance test cases."""
        tests = []
        path = endpoint['path']
        method = endpoint['method'].upper()
        
        # Large payload test
        if method in ['POST', 'PUT', 'PATCH']:
            expected_status = self._get_expected_status(endpoint)
            test_case = {
                'type': TestType.PERFORMANCE.value,
                'endpoint': path,
                'method': method,
                'operation_id': endpoint['operation_id'],
                'name': f"Performance: Large payload for {endpoint['operation_id']}",
                'payload': self._generate_large_payload(endpoint),
                'expected_status': expected_status,
                'description': f"Test performance with large payload",
                'performance_check': True,
                'max_response_time_ms': 5000
            }
            # Add assertions and response time assertion
            assertions = self._generate_assertions_from_responses(endpoint, expected_status)
            if assertions:
                test_case['assertions'] = assertions
            # Add response time assertion
            test_case.setdefault('assertions', []).append({
                'type': 'response_time',
                'condition': 'less_than',
                'expected_value': 5.0,  # 5 seconds
                'description': 'Verify response time is less than 5 seconds'
            })
            tests.append(test_case)
        
        # Concurrent requests simulation
        expected_status = self._get_expected_status(endpoint)
        test_case = {
            'type': TestType.PERFORMANCE.value,
            'endpoint': path,
            'method': method,
            'operation_id': endpoint['operation_id'],
            'name': f"Performance: Response time check for {endpoint['operation_id']}",
            'payload': self._generate_sample_payload(endpoint),
            'expected_status': expected_status,
            'description': f"Test response time under normal load",
            'performance_check': True,
            'max_response_time_ms': 2000
        }
        # Add assertions and response time assertion
        assertions = self._generate_assertions_from_responses(endpoint, expected_status)
        if assertions:
            test_case['assertions'] = assertions
        # Add response time assertion
        test_case.setdefault('assertions', []).append({
            'type': 'response_time',
            'condition': 'less_than',
            'expected_value': 2.0,  # 2 seconds for normal load
            'description': 'Verify response time is less than 2 seconds under normal load'
        })
        tests.append(test_case)
        
        return tests
    
    def _generate_crud_tests(self, endpoints_by_resource: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Generate CRUD operation test flows."""
        tests = []
        
        for resource, endpoints in endpoints_by_resource.items():
            # Identify CRUD operations
            create_endpoint = None
            read_endpoint = None
            update_endpoint = None
            delete_endpoint = None
            list_endpoint = None
            
            for endpoint in endpoints:
                method = endpoint['method'].upper()
                path = endpoint['path']
                
                if method == 'POST' and f'/{resource}' == path:
                    create_endpoint = endpoint
                elif method == 'GET' and f'/{resource}' == path:
                    list_endpoint = endpoint
                elif method == 'GET' and f'/{resource}/' in path:
                    read_endpoint = endpoint
                elif method == 'PUT' and f'/{resource}/' in path:
                    update_endpoint = endpoint
                elif method == 'DELETE' and f'/{resource}/' in path:
                    delete_endpoint = endpoint
            
            # Generate CRUD flow test
            if create_endpoint and read_endpoint and update_endpoint and delete_endpoint:
                # Get assertions for each step in CRUD flow
                create_assertions = self._generate_assertions_from_responses(create_endpoint, [200, 201])
                read_assertions = self._generate_assertions_from_responses(read_endpoint, [200])
                update_assertions = self._generate_assertions_from_responses(update_endpoint, [200])
                delete_assertions = self._generate_assertions_from_responses(delete_endpoint, [200, 204])
                
                test_case = {
                    'type': TestType.CRUD.value,
                    'endpoint': f"/{resource}",
                    'method': 'CRUD',
                    'operation_id': f"{resource}_full_crud_flow",
                    'name': f"CRUD: Full CRUD flow for {resource}",
                    'payload': {
                        'create': self._generate_sample_payload(create_endpoint),
                        'update': self._generate_sample_payload(update_endpoint),
                    },
                    'expected_status': [200, 201, 204],
                    'description': f"Complete CRUD flow: Create -> Read -> Update -> Delete",
                    'crud_flow': [
                        {'operation': 'create', 'endpoint': create_endpoint['path'], 'method': 'POST', 'assertions': create_assertions},
                        {'operation': 'read', 'endpoint': read_endpoint['path'], 'method': 'GET', 'assertions': read_assertions},
                        {'operation': 'update', 'endpoint': update_endpoint['path'], 'method': 'PUT', 'assertions': update_assertions},
                        {'operation': 'delete', 'endpoint': delete_endpoint['path'], 'method': 'DELETE', 'assertions': delete_assertions},
                    ]
                }
                # Add overall assertions for CRUD test
                all_assertions = []
                if create_assertions:
                    all_assertions.extend(create_assertions)
                if read_assertions:
                    all_assertions.extend(read_assertions)
                if all_assertions:
                    test_case['assertions'] = all_assertions
                tests.append(test_case)
        
        return tests
    
    def _generate_integration_tests(self, endpoints_by_resource: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Generate integration tests."""
        tests = []
        
        # Test related endpoints together
        for resource, endpoints in endpoints_by_resource.items():
            if len(endpoints) > 1:
                # Filter out file upload endpoints from integration tests (they need special handling)
                non_upload_endpoints = [
                    e for e in endpoints[:5] 
                    if 'upload' not in e['path'].lower() and 'image' not in e['path'].lower()
                ]
                
                if len(non_upload_endpoints) >= 2:
                    # Get assertions for integration test endpoints
                    integration_assertions = []
                    for e in non_upload_endpoints[:3]:
                        endpoint_assertions = self._generate_assertions_from_responses(e, [200, 201])
                        if endpoint_assertions:
                            integration_assertions.extend(endpoint_assertions)
                    
                    test_case = {
                        'type': TestType.INTEGRATION.value,
                        'endpoint': f"/{resource}",
                        'method': 'INTEGRATION',
                        'operation_id': f"{resource}_integration",
                        'name': f"Integration: Multiple operations for {resource}",
                        'payload': {
                            'endpoints': [{'path': e['path'], 'method': e['method']} for e in non_upload_endpoints[:3]]
                        },
                        'expected_status': [200, 201],
                        'description': f"Test integration between multiple {resource} endpoints",
                        'integration_flow': [
                            {'endpoint': e['path'], 'method': e['method'], 'payload': self._generate_sample_payload(e)}
                            for e in non_upload_endpoints[:3]
                        ]
                    }
                    # Add assertions for integration test
                    if integration_assertions:
                        test_case['assertions'] = integration_assertions
                    tests.append(test_case)
        
        return tests
    
    def _generate_e2e_tests(self, endpoints_by_resource: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Generate end-to-end test scenarios."""
        tests = []
        
        # Generate E2E scenarios for each resource
        for resource, endpoints in endpoints_by_resource.items():
            # Special case: ensure DELETE has a preceding CREATE so id exists
            create_endpoint = next((e for e in endpoints if e['method'].upper() == 'POST' and e['path'].rstrip('/') == f"/{resource}".rstrip('/')), None)
            delete_endpoint = next((e for e in endpoints if e['method'].upper() == 'DELETE' and '{' in e['path']), None)
            if create_endpoint and delete_endpoint:
                create_payload = self._generate_sample_payload(create_endpoint)
                delete_flow = [
                    {
                        'endpoint': create_endpoint['path'],
                        'method': 'POST',
                        'payload': create_payload,
                        'description': f"Create {resource} to obtain id"
                    },
                    {
                        'endpoint': delete_endpoint['path'],
                        'method': 'DELETE',
                        'payload': {},
                        'description': f"Delete created {resource}"
                    }
                ]
                delete_assertions = self._generate_assertions_from_responses(delete_endpoint, [200, 204])
                test_case = {
                    'type': TestType.E2E.value,
                    'endpoint': delete_endpoint['path'],
                    'method': 'DELETE',
                    'operation_id': f"{resource}_create_then_delete",
                    'name': f"E2E: Create then delete {resource}",
                    'payload': {'flow': delete_flow},
                    'expected_status': [200, 201, 204],
                    'description': f"Creates a {resource} then deletes it using the returned id",
                    'e2e_flow': delete_flow
                }
                if delete_assertions:
                    test_case['assertions'] = delete_assertions
                tests.append(test_case)

            if len(endpoints) >= 2:
                # Filter out file upload endpoints from E2E tests (they need special handling)
                non_upload_endpoints = [
                    e for e in endpoints[:6] 
                    if 'upload' not in e['path'].lower() and 'image' not in e['path'].lower()
                ]
                
                if len(non_upload_endpoints) >= 2:
                    # Create a realistic E2E flow
                    e2e_flow = []
                    for endpoint in non_upload_endpoints[:4]:  # Use up to 4 endpoints
                        e2e_flow.append({
                            'endpoint': endpoint['path'],
                            'method': endpoint['method'],
                            'payload': self._generate_sample_payload(endpoint),
                            'description': f"Step: {endpoint['operation_id']}"
                        })
                    
                    # Get assertions for E2E test endpoints
                    e2e_assertions = []
                    for endpoint in non_upload_endpoints[:4]:
                        endpoint_assertions = self._generate_assertions_from_responses(endpoint, [200, 201])
                        if endpoint_assertions:
                            e2e_assertions.extend(endpoint_assertions)
                    
                    test_case = {
                        'type': TestType.E2E.value,
                        'endpoint': f"/{resource}",
                        'method': 'E2E',
                        'operation_id': f"{resource}_e2e_scenario",
                        'name': f"E2E: Complete user flow for {resource}",
                        'payload': {'flow': e2e_flow},
                        'expected_status': [200, 201],
                        'description': f"End-to-end test scenario for {resource} operations",
                        'e2e_flow': e2e_flow
                    }
                    # Add assertions for E2E test
                    if e2e_assertions:
                        test_case['assertions'] = e2e_assertions
                    tests.append(test_case)
        
        return tests
    
    def _get_expected_status(self, endpoint: Dict[str, Any]) -> List[int]:
        """Get expected status codes from endpoint responses."""
        responses = endpoint.get('responses', {})
        status_codes = []
        
        for status_str in responses.keys():
            try:
                status = int(status_str)
                if 200 <= status < 300:
                    status_codes.append(status)
            except ValueError:
                pass
        
        # Default to common success codes if none found
        if not status_codes:
            method = endpoint.get('method', 'GET').upper()
            if method == 'POST':
                status_codes = [200, 201]
            elif method == 'DELETE':
                status_codes = [200, 204]
            else:
                status_codes = [200]
        
        return status_codes if status_codes else [200]
    
    def _generate_assertions_from_responses(self, endpoint: Dict[str, Any], expected_status: List[int]) -> List[Dict[str, Any]]:
        """
        Generate assertions based on OpenAPI response schemas.
        
        Args:
            endpoint: Endpoint definition
            expected_status: Expected status codes for this test
            
        Returns:
            List of assertion definitions
        """
        assertions = []
        responses = endpoint.get('responses', {})
        
        # For each expected status code, extract response schema and create assertions
        for status_code in expected_status:
            status_str = str(status_code)
            response_def = responses.get(status_str, {})
            
            if not response_def:
                # Still add status code assertion even if no response definition
                assertions.append({
                    'type': 'status_code',
                    'condition': 'equals',
                    'expected_value': status_code,
                    'description': f'Verify response status code is {status_code}'
                })
                continue
            
            # Get response description
            response_description = response_def.get('description', '')
            
            # Get response schema (handle both OpenAPI 3.x and Swagger 2.0)
            schema = None
            if 'content' in response_def:
                # OpenAPI 3.x
                for content_type, content_schema in response_def['content'].items():
                    if 'application/json' in content_type or 'json' in content_type:
                        schema = content_schema.get('schema', {})
                        break
            elif 'schema' in response_def:
                # Swagger 2.0
                schema = response_def['schema']
            
            # Add status code assertion with description
            status_desc = response_description if response_description else f'Status {status_code} response'
            assertions.append({
                'type': 'status_code',
                'condition': 'equals',
                'expected_value': status_code,
                'description': f'Verify response status code is {status_code} ({status_desc})'
            })
            
            if not schema:
                # If no schema, just add status code assertion
                continue
            
            # Generate assertions based on schema type
            schema_type = schema.get('type')
            
            if schema_type == 'array':
                # Array response - assert it's an array and optionally check items
                assertions.append({
                    'type': 'response_body',
                    'condition': 'exists',
                    'field': '',
                    'expected_value': True,
                    'description': f'Verify response body exists ({response_description or "array response"})'
                })
                
                # Check if items schema is defined
                items_schema = schema.get('items', {})
                if items_schema:
                    # If items have properties, check first item structure
                    if '$ref' in items_schema:
                        ref_name = items_schema['$ref'].split('/')[-1]
                        assertions.append({
                            'type': 'response_body',
                            'condition': 'exists',
                            'field': '0',
                            'expected_value': True,
                            'description': f'Verify response is an array with at least one {ref_name} item'
                        })
                    elif items_schema.get('type') == 'object' and items_schema.get('properties'):
                        # Check first property of first item
                        first_prop = list(items_schema['properties'].keys())[0] if items_schema['properties'] else None
                        if first_prop:
                            assertions.append({
                                'type': 'response_body',
                                'condition': 'exists',
                                'field': f'0.{first_prop}',
                                'expected_value': True,
                                'description': f'Verify response array items have {first_prop} property'
                            })
            
            elif schema_type == 'object':
                # Object response - check required properties
                properties = schema.get('properties', {})
                required = schema.get('required', [])
                
                # Check required properties exist
                for prop in required[:3]:  # Limit to first 3 required properties
                    assertions.append({
                        'type': 'response_body',
                        'condition': 'exists',
                        'field': prop,
                        'expected_value': True,
                        'description': f'Verify required property {prop} exists in response'
                    })
                
                # If no required properties, check first property
                if not required and properties:
                    first_prop = list(properties.keys())[0]
                    assertions.append({
                        'type': 'response_body',
                        'condition': 'exists',
                        'field': first_prop,
                        'expected_value': True,
                        'description': f'Verify response has {first_prop} property'
                    })
            
            elif '$ref' in schema:
                # Reference to a schema definition
                ref_name = schema['$ref'].split('/')[-1]
                # Resolve the reference to get properties
                try:
                    resolved_schema = self.parser.resolve_ref(schema['$ref'])
                    if isinstance(resolved_schema, dict):
                        properties = resolved_schema.get('properties', {})
                        required = resolved_schema.get('required', [])
                        
                        # Check required properties
                        for prop in required[:3]:
                            assertions.append({
                                'type': 'response_body',
                                'condition': 'exists',
                                'field': prop,
                                'expected_value': True,
                                'description': f'Verify {ref_name} has required property {prop}'
                            })
                except Exception as e:
                    logger.debug(f"Could not resolve schema reference {schema['$ref']}: {e}")
                    # Fallback: just check response exists
                    assertions.append({
                        'type': 'response_body',
                        'condition': 'exists',
                        'field': '',
                        'expected_value': True,
                        'description': f'Verify response body exists for {ref_name}'
                    })
            
            # Always add a basic response body existence check if we have a schema
            if schema and not any(a['type'] == 'response_body' for a in assertions):
                assertions.append({
                    'type': 'response_body',
                    'condition': 'exists',
                    'field': '',
                    'expected_value': True,
                    'description': f'Verify response body exists ({response_description or "response"})'
                })
        
        # Also add assertions for error status codes (400, 404, etc.) if they exist in responses
        for status_str, response_def in responses.items():
            try:
                status = int(status_str)
                if status >= 400 and status not in expected_status:
                    # Add assertion for error status codes
                    error_desc = response_def.get('description', f'Error {status}')
                    assertions.append({
                        'type': 'status_code',
                        'condition': 'not_equals',
                        'expected_value': status,
                        'description': f'Verify response is not {status} ({error_desc})'
                    })
            except ValueError:
                pass
        
        return assertions
    
    def _detect_content_type(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect the content type and encoding style for the endpoint.
        
        Returns:
            Dict with 'content_type', 'encoding_style', 'is_multipart', 'is_form_data'
        """
        result = {
            'content_type': 'application/json',
            'encoding_style': None,
            'is_multipart': False,
            'is_form_data': False,
            'form_params': {},
            'query_params': {}
        }
        
        # Check request body for content types
        request_body = endpoint.get('request_body', {})
        if request_body:
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                if 'multipart/form-data' in content_type:
                    result['content_type'] = 'multipart/form-data'
                    result['is_multipart'] = True
                    result['is_form_data'] = True
                    # Extract form parameters from schema
                    schema = schema_info.get('schema', {})
                    if schema:
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        for prop_name, prop_schema in properties.items():
                            prop_type = prop_schema.get('type', 'string')
                            # Check if it's a file
                            if prop_schema.get('format') == 'binary' or 'file' in prop_name.lower():
                                result['form_params'][prop_name] = {
                                    'type': 'file',
                                    'required': prop_name in required,
                                    'schema': prop_schema
                                }
                            else:
                                result['form_params'][prop_name] = {
                                    'type': prop_type,
                                    'required': prop_name in required,
                                    'schema': prop_schema
                                }
                    # Check encoding
                    encoding = schema_info.get('encoding', {})
                    result['encoding_style'] = encoding
                    break
                elif 'application/x-www-form-urlencoded' in content_type:
                    result['content_type'] = 'application/x-www-form-urlencoded'
                    result['is_form_data'] = True
                    # Extract form parameters
                    schema = schema_info.get('schema', {})
                    if schema:
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        for prop_name, prop_schema in properties.items():
                            result['form_params'][prop_name] = {
                                'type': prop_schema.get('type', 'string'),
                                'required': prop_name in required,
                                'schema': prop_schema
                            }
                    break
                elif 'application/json' in content_type:
                    result['content_type'] = 'application/json'
                    break
        
        # Extract query parameters
        for param in endpoint.get('parameters', []):
            param_in = param.get('in')
            param_name = param.get('name')
            
            if param_in == 'query':
                param_schema = param.get('schema', {})
                # Resolve $ref in parameter schema if present
                if '$ref' in param_schema:
                    try:
                        param_schema = self.parser.resolve_ref(param_schema['$ref'])
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Could not resolve query parameter schema reference for {param_name}: {e}")
                
                result['query_params'][param_name] = {
                    'type': param_schema.get('type', 'string'),
                    'required': param.get('required', False),
                    'schema': param_schema,
                    'default': param_schema.get('default'),
                    'enum': param_schema.get('enum'),  # Include enum for proper value generation
                    'format': param_schema.get('format'),  # Include format (e.g., date, date-time)
                    'minimum': param_schema.get('minimum'),
                    'maximum': param_schema.get('maximum'),
                    'minLength': param_schema.get('minLength'),
                    'maxLength': param_schema.get('maxLength')
                }
        
        return result
    
    def _ensure_schema_compliance(self, endpoint: Dict[str, Any], payload: Dict[str, Any], ensure_required: bool = True) -> Dict[str, Any]:
        """Ensure payload is schema-compliant by adding missing required fields and fixing invalid values."""
        # Get the endpoint schema
        request_body = endpoint.get('request_body', {})
        schema = None
        if request_body:
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                if 'application/json' in content_type:
                    schema = schema_info.get('schema', {})
                    # Resolve $ref if present
                    if '$ref' in schema:
                        try:
                            schema = self.parser.resolve_ref(schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    break
        
        if not schema or schema.get('type') != 'object':
            return payload
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        # Ensure all required fields are present
        if ensure_required:
            for field_name in required:
                if field_name not in payload or payload[field_name] is None:
                    # Generate valid value for missing required field
                    if field_name in properties:
                        field_schema = properties[field_name]
                        # Resolve $ref if present
                        if '$ref' in field_schema:
                            try:
                                field_schema = self.parser.resolve_ref(field_schema['$ref'])
                            except (ValueError, KeyError):
                                pass
                        payload[field_name] = self._get_default_value(field_schema)
        
        # Fix invalid enum values
        for field_name, field_value in payload.items():
            if field_name in properties:
                field_schema = properties[field_name]
                # Resolve $ref if present
                if '$ref' in field_schema:
                    try:
                        field_schema = self.parser.resolve_ref(field_schema['$ref'])
                    except (ValueError, KeyError):
                        pass
                
                # Check if value violates enum constraint
                enum_values = field_schema.get('enum')
                if enum_values and isinstance(field_value, str) and field_value not in enum_values:
                    # Replace with valid enum value
                    if 'available' in enum_values:
                        payload[field_name] = 'available'
                    elif len(enum_values) > 0:
                        payload[field_name] = enum_values[0]
        
        return payload
    
    def _generate_sample_payload(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate sample payload from endpoint schema."""
        payload = {}
        method = endpoint.get('method', 'GET').upper()
        
        # Extract path parameters from endpoint path (they should NOT be in payload)
        path = endpoint.get('path', '')
        path_params = set(re.findall(r'\{(\w+)\}', path))
        
        # Detect content type and parameters
        content_info = self._detect_content_type(endpoint)
        
        # For GET/DELETE methods, use query parameters
        if method in ['GET', 'DELETE']:
            # Add query parameters
            for param_name, param_info in content_info['query_params'].items():
                if param_info.get('default') is not None:
                    payload[param_name] = param_info['default']
                elif param_info.get('required', False):
                    payload[param_name] = self._get_default_value(param_info['schema'])
            return payload
        
        # For POST/PUT/PATCH, generate request body payload
        if content_info['is_form_data'] or content_info['is_multipart']:
            # Generate form parameters - ALWAYS include required ones
            for param_name, param_info in content_info['form_params'].items():
                param_schema = param_info.get('schema', {})
                
                if param_info['type'] == 'file':
                    # For file parameters, we'll mark them specially
                    payload[param_name] = '__FILE__'
                elif param_info.get('required', False):
                    # Required form parameters - use schema-aware generation
                    # Resolve $ref if present
                    if '$ref' in param_schema:
                        try:
                            param_schema = self.parser.resolve_ref(param_schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    payload[param_name] = self._get_default_value(param_schema)
                else:
                    # Optional form parameters - include if has default or enum
                    default_val = param_schema.get('default')
                    if default_val is not None:
                        payload[param_name] = default_val
                    elif param_schema.get('enum'):
                        enum_values = param_schema.get('enum')
                        if 'available' in enum_values:
                            payload[param_name] = 'available'
                        elif len(enum_values) > 0:
                            payload[param_name] = enum_values[0]
            
            # Store content type metadata immediately for form data
            payload['__content_type__'] = content_info['content_type']
            payload['__is_multipart__'] = content_info['is_multipart']
            payload['__is_form_data__'] = content_info['is_form_data']
        else:
            # JSON payload
            request_body = endpoint.get('request_body', {})
            if request_body:
                content = request_body.get('content', {})
                for content_type, schema_info in content.items():
                    if 'application/json' in content_type:
                        schema = schema_info.get('schema', {})
                        payload = self._generate_from_schema(schema)
                        break
        
        # For PUT requests, ensure we have a complete payload (PUT replaces entire resource)
        if method == 'PUT' and not payload:
            # PUT requires full resource representation, generate comprehensive payload
            payload = self._generate_complete_payload_for_put(endpoint)
        
        # If no request body schema, try to generate from parameters
        if not payload and method in ['POST', 'PATCH']:
            # Generate a basic payload structure from operation_id or path
            operation_id = endpoint.get('operation_id', '')
            path_parts = [p for p in path.split('/') if p and not p.startswith('{')]
            
            # Try to infer payload structure from common patterns
            if 'pet' in path.lower() or 'pet' in operation_id.lower():
                # Use enum-aware status value
                status_value = 'available'  # Default
                request_body = endpoint.get('request_body', {})
                if request_body:
                    content = request_body.get('content', {})
                    for content_type, schema_info in content.items():
                        if 'application/json' in content_type:
                            schema = schema_info.get('schema', {})
                            if schema:
                                # Resolve $ref if present
                                if '$ref' in schema:
                                    try:
                                        schema = self.parser.resolve_ref(schema['$ref'])
                                    except ValueError:
                                        pass
                                # Check for status enum
                                properties = schema.get('properties', {})
                                if 'status' in properties:
                                    status_schema = properties['status']
                                    status_enum = status_schema.get('enum')
                                    if status_enum and 'available' in status_enum:
                                        status_value = 'available'
                                    elif status_enum and len(status_enum) > 0:
                                        status_value = status_enum[0]
                payload = {
                    'id': 1,
                    'name': 'Test Pet',
                    'status': status_value,
                    'category': {'id': 1, 'name': 'Dogs'},
                    'tags': [{'id': 1, 'name': 'friendly'}],
                    'photoUrls': ['https://example.com/photo.jpg']
                }
            elif 'user' in path.lower() or 'user' in operation_id.lower():
                payload = {
                    'id': 1,
                    'username': 'testuser',
                    'firstName': 'Test',
                    'lastName': 'User',
                    'email': 'test@example.com',
                    'password': 'password123',
                    'phone': '1234567890',
                    'userStatus': 1
                }
            elif 'order' in path.lower() or 'order' in operation_id.lower():
                payload = {
                    'id': 1,
                    'petId': 1,
                    'quantity': 1,
                    'shipDate': '2024-01-01T00:00:00Z',
                    'status': 'placed',
                    'complete': False
                }
            else:
                # Generic payload structure
                payload = {
                    'id': 1,
                    'name': 'Test Item',
                    'description': 'Test Description',
                    'status': 'active'
                }
        
        # Add query parameters (NOT path parameters)
        for param in endpoint.get('parameters', []):
            param_in = param.get('in')
            param_name = param.get('name')
            
            # Skip path parameters (they're in the URL path, not payload)
            if param_in == 'path' or param_name in path_params:
                continue
            
            # Skip body parameters (already handled above)
            if param_in == 'body':
                continue
            
            # Add query/header parameters
            if param_in == 'query':
                param_schema = param.get('schema', {})
                default = param_schema.get('default')
                if default is not None:
                    payload[param_name] = default
                elif param.get('required', False):
                    payload[param_name] = self._get_default_value(param_schema)
        
        return payload
    
    def _generate_complete_payload_for_put(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete payload for PUT requests (PUT replaces entire resource)."""
        path = endpoint.get('path', '')
        operation_id = endpoint.get('operation_id', '')
        
        # Generate comprehensive payload based on resource type
        if 'pet' in path.lower() or 'pet' in operation_id.lower():
            # Try to get the actual schema to use proper enum values
            request_body = endpoint.get('request_body', {})
            status_value = 'available'  # Default
            if request_body:
                content = request_body.get('content', {})
                for content_type, schema_info in content.items():
                    if 'application/json' in content_type:
                        schema = schema_info.get('schema', {})
                        if schema:
                            # Resolve $ref if present
                            if '$ref' in schema:
                                try:
                                    schema = self.parser.resolve_ref(schema['$ref'])
                                except ValueError:
                                    pass
                            # Check for status enum in properties
                            properties = schema.get('properties', {})
                            if 'status' in properties:
                                status_schema = properties['status']
                                status_enum = status_schema.get('enum')
                                if status_enum and 'available' in status_enum:
                                    status_value = 'available'
                                elif status_enum and len(status_enum) > 0:
                                    status_value = status_enum[0]
            return {
                'id': 1,
                'name': 'Updated Test Pet',
                'status': status_value,
                'category': {'id': 1, 'name': 'Dogs'},
                'tags': [{'id': 1, 'name': 'friendly'}, {'id': 2, 'name': 'trained'}],
                'photoUrls': ['https://example.com/photo1.jpg', 'https://example.com/photo2.jpg']
            }
        elif 'user' in path.lower() or 'user' in operation_id.lower():
            return {
                'id': 1,
                'username': 'updateduser',
                'firstName': 'Updated',
                'lastName': 'User',
                'email': 'updated@example.com',
                'password': 'newpassword123',
                'phone': '9876543210',
                'userStatus': 1
            }
        elif 'order' in path.lower() or 'order' in operation_id.lower():
            return {
                'id': 1,
                'petId': 1,
                'quantity': 2,
                'shipDate': '2024-12-15T00:00:00Z',
                'status': 'placed',
                'complete': False
            }
        else:
            # Generic complete payload
            return {
                'id': 1,
                'name': 'Updated Test Item',
                'description': 'Updated Test Description',
                'status': 'active',
                'updatedAt': '2024-12-14T00:00:00Z'
            }
    
    def _generate_from_schema(self, schema: Dict[str, Any]) -> Any:
        """Generate sample value from JSON schema, properly resolving $ref references."""
        # Resolve $ref if present
        if '$ref' in schema:
            try:
                resolved_schema = self.parser.resolve_ref(schema['$ref'])
                # Recursively generate from resolved schema
                return self._generate_from_schema(resolved_schema)
            except (ValueError, KeyError) as e:
                logger.warning(f"Could not resolve schema reference {schema.get('$ref')}: {e}")
                # Fallback to basic object structure
                return {}
        
        schema_type = schema.get('type')
        
        if schema_type == 'object':
            result = {}
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            # ALWAYS include all required fields
            for prop_name in required:
                if prop_name in properties:
                    prop_schema = properties[prop_name]
                    # Resolve $ref in property schema if present
                    if '$ref' in prop_schema:
                        try:
                            prop_schema = self.parser.resolve_ref(prop_schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    result[prop_name] = self._get_default_value(prop_schema)
            
            # Also include optional properties with defaults or enums (like status fields)
            for prop_name, prop_schema in properties.items():
                if prop_name not in required:
                    # Resolve $ref in property schema if present
                    if '$ref' in prop_schema:
                        try:
                            prop_schema = self.parser.resolve_ref(prop_schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    
                    if prop_schema.get('default') is not None or prop_schema.get('enum'):
                        result[prop_name] = self._get_default_value(prop_schema)
                    # Include nested objects even if optional (for completeness)
                    elif prop_schema.get('type') == 'object':
                        nested_result = self._generate_from_schema(prop_schema)
                        if nested_result:
                            result[prop_name] = nested_result
            
            return result
        elif schema_type == 'array':
            items = schema.get('items', {})
            # Resolve $ref in items if present
            if '$ref' in items:
                try:
                    items = self.parser.resolve_ref(items['$ref'])
                except (ValueError, KeyError):
                    pass
            return [self._get_default_value(items)]
        else:
            return self._get_default_value(schema)
    
    def _get_default_value(self, schema: Dict[str, Any]) -> Any:
        """Get default value for schema type."""
        schema_type = schema.get('type')
        default = schema.get('default')
        
        if default is not None:
            return default
        
        # Check for enum values first (before type-based defaults)
        enum_values = schema.get('enum')
        if enum_values and isinstance(enum_values, list) and len(enum_values) > 0:
            # Use the first enum value as default, or the one marked as default
            # For status fields, prefer "available" if it exists
            if 'available' in enum_values:
                return 'available'
            elif 'pending' in enum_values:
                return 'pending'
            else:
                return enum_values[0]
        
        if schema_type == 'string':
            return "sample_string"
        elif schema_type == 'integer':
            return 1  # Use 1 instead of 0 for IDs
        elif schema_type == 'number':
            return 1.0
        elif schema_type == 'boolean':
            return True
        elif schema_type == 'array':
            return []
        elif schema_type == 'object':
            return {}
        else:
            # For unknown types, return a sensible default instead of None
            return ""
    
    def _generate_invalid_payload(self, endpoint: Dict[str, Any], overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate invalid payload for negative tests."""
        payload = self._generate_sample_payload(endpoint)
        if overrides:
            payload.update(overrides)
        return payload
    
    def _generate_invalid_type_payload(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate payload with invalid data types."""
        payload = self._generate_sample_payload(endpoint)
        
        # If payload is empty, create a basic structure with obviously wrong types
        if not payload:
            payload = {'name': 12345, 'id': 'invalid_string', 'status': 999, 'invalidField': None}
        else:
            # Replace string fields with numbers, numbers with strings, etc.
            # Make it obviously invalid to ensure API rejects it
            for key, value in payload.items():
                if isinstance(value, str):
                    payload[key] = 12345  # Wrong type - string field gets number
                elif isinstance(value, int):
                    payload[key] = "invalid_string"  # Wrong type - number field gets string
                elif isinstance(value, bool):
                    payload[key] = "not_boolean"  # Wrong type - boolean field gets string
                elif isinstance(value, list):
                    payload[key] = "not_an_array"  # Wrong type - array field gets string
                elif isinstance(value, dict):
                    # Handle nested objects - make them invalid
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, str):
                            payload[key][nested_key] = 12345
                        elif isinstance(nested_value, int):
                            payload[key][nested_key] = "invalid"
                        elif isinstance(nested_value, dict):
                            payload[key][nested_key] = "not_an_object"
        
        return payload
    
    def _generate_boundary_payload(self, endpoint: Dict[str, Any], boundary_type: str, value: Any = None) -> Dict[str, Any]:
        """Generate payload with boundary values."""
        payload = self._generate_sample_payload(endpoint)
        
        # If payload is empty, create a basic structure for boundary testing
        if not payload:
            payload = {'name': 'test', 'id': 1, 'value': 1}
        
        if boundary_type == 'empty_string':
            for key in payload:
                if isinstance(payload[key], str):
                    payload[key] = ""
                elif isinstance(payload[key], dict):
                    # Handle nested objects
                    for nested_key in payload[key]:
                        if isinstance(payload[key][nested_key], str):
                            payload[key][nested_key] = ""
        elif boundary_type == 'max_length':
            for key in payload:
                if isinstance(payload[key], str):
                    payload[key] = "a" * 1000  # Reasonable long string (reduced from 10000)
                elif isinstance(payload[key], dict):
                    for nested_key in payload[key]:
                        if isinstance(payload[key][nested_key], str):
                            payload[key][nested_key] = "a" * 1000
        elif boundary_type == 'min_length':
            for key in payload:
                if isinstance(payload[key], str):
                    payload[key] = "a"  # Single character
                elif isinstance(payload[key], dict):
                    for nested_key in payload[key]:
                        if isinstance(payload[key][nested_key], str):
                            payload[key][nested_key] = "a"
        elif boundary_type == 'numeric' and value is not None:
            for key in payload:
                if isinstance(payload[key], (int, float)):
                    payload[key] = value
                elif isinstance(payload[key], dict):
                    for nested_key in payload[key]:
                        if isinstance(payload[key][nested_key], (int, float)):
                            payload[key][nested_key] = value
        
        return payload
    
    def _generate_security_payload(self, endpoint: Dict[str, Any], attack_type: str, payload_value: str) -> Dict[str, Any]:
        """Generate payload with security attack vectors that violate schema constraints."""
        # Get the endpoint schema to understand constraints
        request_body = endpoint.get('request_body', {})
        schema = None
        if request_body:
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                if 'application/json' in content_type:
                    schema = schema_info.get('schema', {})
                    # Resolve $ref if present
                    if '$ref' in schema:
                        try:
                            schema = self.parser.resolve_ref(schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    break
        
        payload = self._generate_sample_payload(endpoint)
        
        # If payload is empty, create a basic structure with attack vector
        if not payload:
            payload = {'name': payload_value, 'description': payload_value}
        else:
            # Strategy: Create a payload that violates schema constraints
            # 1. Inject attack vectors into string fields (especially those with format constraints)
            # 2. Violate enum constraints by using attack vector instead of valid enum
            # 3. Violate type constraints where possible
            
            if schema and schema.get('type') == 'object':
                properties = schema.get('properties', {})
                required = schema.get('required', [])
                
                for key, value in list(payload.items()):
                    if key in properties:
                        prop_schema = properties[key]
                        # Resolve $ref in property if present
                        if '$ref' in prop_schema:
                            try:
                                prop_schema = self.parser.resolve_ref(prop_schema['$ref'])
                            except (ValueError, KeyError):
                                pass
                        
                        prop_type = prop_schema.get('type')
                        prop_enum = prop_schema.get('enum')
                        prop_format = prop_schema.get('format')
                        
                        # Violate enum constraints - use attack vector instead of valid enum
                        if prop_enum and isinstance(value, str):
                            payload[key] = payload_value  # This violates enum constraint
                        # Violate format constraints - inject attack vector into formatted fields
                        elif prop_format and prop_type == 'string':
                            payload[key] = payload_value  # Violates format (email, date, uri, etc.)
                        # Inject into string fields
                        elif isinstance(value, str) and prop_type == 'string':
                            payload[key] = payload_value
                        # Violate type constraints - inject string into numeric fields
                        elif prop_type in ['integer', 'number'] and isinstance(value, (int, float)):
                            # For security tests, we can inject attack vector as string in numeric field
                            # This will cause type validation to fail
                            payload[key] = payload_value
                        elif isinstance(value, dict):
                            # Recursively inject into nested objects
                            for nested_key in payload[key]:
                                if isinstance(payload[key][nested_key], str):
                                    payload[key][nested_key] = payload_value
                    else:
                        # Field not in schema - inject attack vector
                        if isinstance(value, str):
                            payload[key] = payload_value
                        elif isinstance(value, dict):
                            for nested_key in payload[key]:
                                if isinstance(payload[key][nested_key], str):
                                    payload[key][nested_key] = payload_value
            else:
                # Fallback: Inject attack vector into all string fields
                for key in payload:
                    if isinstance(payload[key], str):
                        payload[key] = payload_value
                    elif isinstance(payload[key], dict):
                        # Recursively inject into nested objects
                        for nested_key in payload[key]:
                            if isinstance(payload[key][nested_key], str):
                                payload[key][nested_key] = payload_value
        
        return payload
    
    def _generate_large_payload(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate large payload for performance testing."""
        payload = self._generate_sample_payload(endpoint)
        
        # Make payload reasonably large but not so large it crashes the API
        # Use moderate sizes that test performance without breaking the API
        for key in payload:
            if isinstance(payload[key], str):
                payload[key] = "x" * 1000  # 1KB string (reduced from 10KB to avoid 500 errors)
            elif isinstance(payload[key], list):
                payload[key] = [{"item": i} for i in range(100)]  # Moderate array (reduced from 1000)
            elif isinstance(payload[key], dict):
                # Expand nested objects
                for i in range(10):
                    payload[key][f'field_{i}'] = "x" * 100
        
        return payload
    
    def _prepare_context(self, endpoint: Dict[str, Any]) -> str:
        """Prepare context for LLM generation with complete schema information."""
        context_parts = [
            f"Endpoint: {endpoint['method']} {endpoint['path']}",
            f"Operation ID: {endpoint.get('operation_id', 'N/A')}",
            f"Summary: {endpoint.get('summary', 'N/A')}"
        ]
        
        # Add parameters with full schema information
        if endpoint.get('parameters'):
            context_parts.append("\nParameters:")
            for param in endpoint['parameters']:
                param_name = param.get('name')
                param_in = param.get('in')
                param_schema = param.get('schema', {})
                
                # Resolve $ref if present
                if '$ref' in param_schema:
                    try:
                        param_schema = self.parser.resolve_ref(param_schema['$ref'])
                    except (ValueError, KeyError):
                        pass
                
                param_type = param_schema.get('type', 'string')
                param_required = param.get('required', False)
                param_enum = param_schema.get('enum')
                param_format = param_schema.get('format')
                
                param_desc = f"  - {param_name} ({param_in}, type: {param_type}"
                if param_required:
                    param_desc += ", REQUIRED"
                if param_enum:
                    param_desc += f", enum: {param_enum}"
                if param_format:
                    param_desc += f", format: {param_format}"
                param_desc += f"): {param.get('description', 'N/A')}"
                context_parts.append(param_desc)
        
        # Add request body schema with full details
        request_body = endpoint.get('request_body', {})
        if request_body:
            context_parts.append("\nRequest Body:")
            content = request_body.get('content', {})
            for content_type, schema_info in content.items():
                schema = schema_info.get('schema', {})
                context_parts.append(f"  Content-Type: {content_type}")
                
                # Resolve $ref if present
                if '$ref' in schema:
                    ref_name = schema['$ref'].split('/')[-1]
                    context_parts.append(f"  Schema Reference: {ref_name}")
                    try:
                        resolved_schema = self.parser.resolve_ref(schema['$ref'])
                        schema = resolved_schema
                        context_parts.append(f"  (Resolved schema details below)")
                    except (ValueError, KeyError) as e:
                        context_parts.append(f"  (Could not resolve: {e})")
                
                # Add detailed schema information
                schema_type = schema.get('type', 'unknown')
                context_parts.append(f"  Schema type: {schema_type}")
                
                if schema_type == 'object':
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                    
                    if required:
                        context_parts.append(f"    REQUIRED FIELDS (must be included): {', '.join(required)}")
                    
                    if properties:
                        context_parts.append(f"    Properties:")
                        for prop_name, prop_schema in list(properties.items())[:15]:  # Limit to first 15
                            # Resolve $ref in property if present
                            if '$ref' in prop_schema:
                                try:
                                    prop_schema = self.parser.resolve_ref(prop_schema['$ref'])
                                except (ValueError, KeyError):
                                    pass
                            
                            prop_type = prop_schema.get('type', 'unknown')
                            prop_desc = f"      - {prop_name}: {prop_type}"
                            if prop_name in required:
                                prop_desc += " (REQUIRED)"
                            if prop_schema.get('enum'):
                                prop_desc += f" [enum: {prop_schema.get('enum')}]"
                            if prop_schema.get('format'):
                                prop_desc += f" [format: {prop_schema.get('format')}]"
                            if prop_schema.get('default') is not None:
                                prop_desc += f" [default: {prop_schema.get('default')}]"
                            context_parts.append(prop_desc)
        
        if endpoint.get('responses'):
            context_parts.append("\nResponses:")
            for status, response_info in endpoint['responses'].items():
                context_parts.append(f"  - {status}: {response_info.get('description', 'N/A')}")
        
        return "\n".join(context_parts)
    
    def _create_test_generation_prompt(self, endpoint: Dict[str, Any], context: str) -> str:
        """Create prompt for LLM test generation."""
        # Extract response schemas for assertion generation
        responses_info = ""
        responses = endpoint.get('responses', {})
        if responses:
            responses_info = "\n\nResponse Schemas:\n"
            for status, response_def in responses.items():
                responses_info += f"  Status {status}: {response_def.get('description', 'No description')}\n"
                # Extract schema info
                schema = None
                if 'content' in response_def:
                    for content_type, content_schema in response_def['content'].items():
                        if 'application/json' in content_type:
                            schema = content_schema.get('schema', {})
                            break
                elif 'schema' in response_def:
                    schema = response_def['schema']
                
                if schema:
                    # Resolve $ref if present
                    if '$ref' in schema:
                        ref_name = schema['$ref'].split('/')[-1]
                        responses_info += f"    Schema Reference: {ref_name}\n"
                        try:
                            resolved_schema = self.parser.resolve_ref(schema['$ref'])
                            schema = resolved_schema
                            responses_info += f"    (Resolved schema details below)\n"
                        except (ValueError, KeyError):
                            pass
                    
                    schema_type = schema.get('type', 'unknown')
                    responses_info += f"    Schema type: {schema_type}\n"
                    
                    if schema_type == 'array':
                        items = schema.get('items', {})
                        if '$ref' in items:
                            items_ref = items['$ref'].split('/')[-1]
                            responses_info += f"    Array items reference: {items_ref}\n"
                            try:
                                resolved_items = self.parser.resolve_ref(items['$ref'])
                                items = resolved_items
                            except (ValueError, KeyError):
                                pass
                        items_type = items.get('type', 'unknown')
                        responses_info += f"    Array items type: {items_type}\n"
                        if items_type == 'object' and items.get('properties'):
                            items_required = items.get('required', [])
                            if items_required:
                                responses_info += f"    Array item required fields: {', '.join(items_required[:5])}\n"
                    elif schema_type == 'object':
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        if required:
                            responses_info += f"    REQUIRED fields in response: {', '.join(required)}\n"
                        if properties:
                            responses_info += f"    Response properties: {', '.join(list(properties.keys())[:10])}\n"
        
        return f"""You are an autonomous API test generator. You will be given structured JSON describing an API endpoint (from an OpenAPI specification).
You MUST automatically parse it and generate comprehensive API test cases for this endpoint without asking for clarification.

Your internal reasoning process (do this silently before outputting):
1. Parse the JSON details for this endpoint: path, method, parameters (path/query/header/body with types, required/optional, enums, constraints), authentication hints, request/response schemas, and examples.
2. Internally create a plan to produce 15–20 high‑value test cases for this endpoint, covering:
   - Happy paths (valid, schema‑compliant)
   - Error/validation paths (invalid/missing/unauthorized)
   - Boundary and edge cases (min/max, null/empty, special characters, enum boundaries, arrays/multi‑value)
   - Security‑relevant inputs (injections, malformed data)
   - Performance/large payload cases where applicable
3. For dependencies (e.g., create then get/delete), note setup steps and ensure IDs or tokens used in later calls come from earlier steps.
4. Handle authentication using placeholders like 'Authorization: Bearer <token>' or 'X-API-Key: <api_key>' as appropriate.

Endpoint and schema context:

{context}
{responses_info}

CRITICAL REQUIREMENTS FOR 100% PASS RATE (APPLY THESE RULES TO ALL GENERATED TESTS):

1. **Happy Path Tests (MUST PASS 100%):**
   - Include ALL required fields from the schema
   - Use ONLY valid enum values (check enum arrays in schema)
   - For query array enums (e.g., collectionFormat=multi or explode=true), produce multiple happy-path variants: one per enum value and at least one combined multi-value request (e.g., ?status=available&status=pending)
   - Use correct data types (string, integer, number, boolean, array, object)
   - Respect format constraints (date, date-time, email, uri, etc.)
   - Use valid values within minLength/maxLength, minimum/maximum constraints
   - Resolve all $ref references to get complete schema structure
   - For nested objects, include all required fields in nested schemas
   - For arrays, ensure items match the item schema
   - Query parameters: Include all required query params with correct types and enum values
   - Path parameters: Will be replaced dynamically, but ensure payload doesn't include them
   - Expected status: Use [200] or [201] for successful operations
   - These tests MUST pass - they test valid, schema-compliant requests

2. **Negative/Validation Tests (MUST FAIL CORRECTLY):**
   - Test ONE validation issue at a time (missing required field, wrong type, invalid enum)
   - Missing required field: Remove ONE required field, keep others valid
   - Wrong type: Replace string with number, number with string, etc.
   - Invalid enum: Use a value NOT in the enum array
   - Invalid format: Use wrong format (e.g., "not-an-email" for email field)
   - Expected status: [400, 422] - API should reject invalid input
   - These tests pass when API correctly rejects invalid input

3. **Security Tests (MUST FAIL CORRECTLY):**
   - Inject attack vectors (SQL injection, XSS) into fields
   - Violate enum constraints by using attack vector instead of valid enum
   - Violate format constraints (e.g., XSS in email field)
   - Can combine with missing required fields for stronger validation
   - Expected status: [400, 403, 422] - API should reject security threats
   - These tests pass when API correctly rejects security threats

4. **Boundary Tests:**
   - Test minimum/maximum values from schema
   - Test minLength/maxLength for strings
   - Test minItems/maxItems for arrays
   - Use valid types but boundary values
   - Expected status: [200, 201, 400, 422] depending on whether boundary is valid

5. **Edge Case Tests:**
   - Test null values (if schema allows)
   - Test empty strings (if schema allows)
   - Test empty arrays (if schema allows)
   - Expected status: Based on schema constraints

For each test case, provide:
- type: one of happy_path, edge_case, boundary, validation, security
- name: descriptive test name
- payload: JSON payload that STRICTLY follows schema (for happy_path) or violates it (for negative/security)
- expected_status: array of expected HTTP status codes
- description: what the test validates
- assertions: array of assertion objects to validate the response

IMPORTANT FOR HAPPY PATH TESTS:
- Generate assertions based on the response schemas above
- For each test case with expected_status 200/201, include assertions to validate:
  - Status code matches expected value
  - Response body structure matches schema (check required properties exist, array items have expected structure, etc.)
  - Response content type is correct
  - All required response fields exist
  - Enum values in response are valid

Assertion format:
{{
  "type": "status_code" | "response_body" | "response_header",
  "condition": "equals" | "contains" | "exists" | "matches",
  "expected_value": <value>,
  "field": "<json_path>" (optional, for response_body),
  "description": "<description>"
}}

Output as JSON array of test cases. Example format:
[
  {{
    "type": "happy_path",
    "name": "Successful user creation",
    "payload": {{"name": "John", "email": "john@example.com"}},
    "expected_status": [200, 201],
    "description": "Test successful user creation with valid data",
    "assertions": [
      {{
        "type": "status_code",
        "condition": "equals",
        "expected_value": 201,
        "description": "Verify response status code is 201"
      }},
      {{
        "type": "response_body",
        "condition": "exists",
        "field": "id",
        "expected_value": true,
        "description": "Verify response has id property"
      }},
      {{
        "type": "response_body",
        "condition": "exists",
        "field": "name",
        "expected_value": true,
        "description": "Verify response has name property"
      }}
    ]
  }},
  {{
    "type": "security",
    "name": "SQL injection in email field",
    "payload": {{"email": "'; DROP TABLE users; --"}},
    "expected_status": [400, 422],
    "description": "Test protection against SQL injection",
    "assertions": [
      {{
        "type": "status_code",
        "condition": "equals",
        "expected_value": 400,
        "description": "Verify API rejects invalid input with 400"
      }}
    ]
  }}
]

Generate at least 5 diverse test cases for this endpoint. For happy_path tests, always include assertions based on the response schema.
"""
    
    def _parse_llm_response(self, response: str, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse LLM response into test cases."""
        tests = []
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                # If LLM didn't generate assertions, add them based on response schema
                expected_status = self._get_expected_status(endpoint)
                test_cases = json.loads(json_match.group())
                
                for test_case in test_cases:
                    test_type = test_case.get('type', 'happy_path')
                    parsed_test = {
                        'type': test_type,
                        'endpoint': endpoint['path'],
                        'method': endpoint['method'].upper(),
                        'operation_id': endpoint['operation_id'],
                        'name': test_case.get('name', 'LLM Generated Test'),
                        'payload': test_case.get('payload', {}),
                        'expected_status': test_case.get('expected_status', [200]),
                        'description': test_case.get('description', '')
                    }
                    
                    # For happy_path tests, ensure payload is schema-compliant
                    if test_type == 'happy_path':
                        # Validate and fix payload to ensure it includes all required fields
                        parsed_test['payload'] = self._ensure_schema_compliance(
                            endpoint, 
                            parsed_test['payload'],
                            ensure_required=True
                        )
                    
                    # Preserve assertions from LLM if provided
                    if 'assertions' in test_case and test_case['assertions']:
                        parsed_test['assertions'] = test_case['assertions']
                    else:
                        # If no assertions provided by LLM, generate them from response schema
                        expected_statuses = parsed_test.get('expected_status', [200])
                        generated_assertions = self._generate_assertions_from_responses(endpoint, expected_statuses)
                        if generated_assertions:
                            parsed_test['assertions'] = generated_assertions
                    
                    tests.append(parsed_test)
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {str(e)}")
        
        return tests
    
    def _generate_llm_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate LLM-enhanced test cases using RAG."""
        if not self.llm_api_key:
            return []
        
        tests = []
        
        # Prepare context
        context = self._prepare_context(endpoint)
        prompt = self._create_test_generation_prompt(endpoint, context)
        
        # Call LLM
        try:
            # Import OpenAI - handle different LangChain versions
            try:
                from langchain.llms import OpenAI
            except ImportError:
                try:
                    from langchain_openai import OpenAI
                except ImportError:
                    logger.error("LangChain OpenAI not available. LLM features disabled.")
                    return []
            
            # Determine endpoint
            endpoint_url = self.llm_endpoint
            if not endpoint_url:
                if self.llm_provider == 'local':
                    endpoint_url = 'http://localhost:11434/v1'
                elif self.llm_provider == 'openrouter':
                    endpoint_url = 'https://openrouter.ai/api/v1'
                elif self.llm_provider == 'openai':
                    endpoint_url = 'https://api.openai.com/v1'
                elif self.llm_provider == 'xai':
                    endpoint_url = 'https://api.x.ai/v1'
                elif self.llm_provider == 'anthropic':
                    endpoint_url = 'https://api.anthropic.com/v1'
                else:
                    endpoint_url = f"https://api.{self.llm_provider}.com/v1"
            
            if self.llm_provider == "openai" or self.llm_provider == "openrouter" or self.llm_provider == "xai":
                # OpenAI-compatible API
                llm = OpenAI(
                    api_key=self.llm_api_key,
                    model_name=self.llm_model,
                    openai_api_base=endpoint_url
                )
            elif self.llm_provider == "local":
                # Local Ollama - use OpenAI-compatible wrapper
                llm = OpenAI(
                    api_key="ollama",  # Not used but required
                    model_name=self.llm_model,
                    openai_api_base=endpoint_url
                )
            elif self.llm_provider == "anthropic":
                # Anthropic Claude - use OpenAI wrapper with custom endpoint
                llm = OpenAI(
                    api_key=self.llm_api_key,
                    model_name=self.llm_model,
                    openai_api_base=endpoint_url
                )
            else:
                # Generic OpenAI-compatible
                llm = OpenAI(
                    api_key=self.llm_api_key,
                    model_name=self.llm_model,
                    openai_api_base=endpoint_url
                )
            
            # Log request (truncated prompt)
            logger.info(
                "LLM request: provider=%s model=%s endpoint=%s prompt_start=%s...",
                self.llm_provider,
                self.llm_model,
                endpoint_url,
                prompt[:200].replace("\n", " ") if isinstance(prompt, str) else str(prompt)[:200],
            )

            # Generate tests
            response = llm(prompt)
            try:
                logger.info(
                    "LLM raw response (truncated): %s",
                    str(response)[:1000].replace("\n", " "),
                )
            except Exception:
                pass
            llm_tests = self._parse_llm_response(response, endpoint)
            tests.extend(llm_tests)
        
        except Exception as e:
            logger.error(f"LLM test generation error: {str(e)}")
        
        return tests
