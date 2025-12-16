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
from faker import Faker
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
        self.faker = Faker()
   
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
        
        # Store all endpoints for related endpoint discovery in LLM prompts
        self.all_endpoints = endpoints
       
        for endpoint in endpoints:
            # If LLM is configured, ONLY use LLM for test generation (no baseline fallback)
            if self.llm_api_key:
                # LLM-enhanced tests - REQUIRED when LLM is configured
                try:
                    llm_tests = self._generate_llm_tests(endpoint)
                    if enabled:
                        llm_tests = [t for t in llm_tests if t.get('type', '').lower() in enabled]
                    if not llm_tests or len(llm_tests) == 0:
                        raise ValueError(f"LLM returned no tests for endpoint {endpoint.get('operation_id', endpoint.get('path'))}")
                    all_tests.extend(llm_tests)
                except Exception as e:
                    logger.error(f"LLM test generation failed for {endpoint['operation_id']}: {str(e)}", exc_info=True)
                    raise RuntimeError(
                        f"LLM test generation failed for endpoint {endpoint.get('operation_id', endpoint.get('path'))}: {str(e)}. "
                        f"No fallback tests will be generated. Please check your LLM configuration and try again."
                    )
            else:
                # Baseline tests - only when LLM is NOT configured
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
        if method == 'DELETE' and re.search(r'{(\w+)}', path):
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
        if method in ['PUT', 'PATCH'] and re.search(r'{(\w+)}', path):
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
        path_params = re.findall(r'{(\w+)}', path)
        for param in path_params:
            # Determine parameter type from OpenAPI spec
            param_type = 'string' # Default
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
                for required_field in required_fields[:3]: # Limit to first 3 to avoid too many tests
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
                        'payload': test_payload, # Valid payload except missing one required field
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
                        'payload': {}, # Completely empty payload
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
                'expected_value': 5.0, # 5 seconds
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
            'expected_value': 2.0, # 2 seconds for normal load
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
                    for endpoint in non_upload_endpoints[:4]: # Use up to 4 endpoints
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
                for prop in required[:3]: # Limit to first 3 required properties
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
                    'enum': param_schema.get('enum'), # Include enum for proper value generation
                    'format': param_schema.get('format'), # Include format (e.g., date, date-time)
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
       
        # Remove fields that don't exist in the schema (LLM might have generated wrong field names)
        valid_payload = {}
        for field_name, field_value in payload.items():
            # Skip metadata fields
            if field_name.startswith('**') and field_name.endswith('**'):
                valid_payload[field_name] = field_value
            elif field_name in properties:
                valid_payload[field_name] = field_value
            else:
                logger.warning(f"Removing field '{field_name}' from payload - not in schema. Schema has: {list(properties.keys())}")
       
        # Ensure all required fields are present
        if ensure_required:
            for field_name in required:
                if field_name not in valid_payload or valid_payload[field_name] is None:
                    # Generate valid value for missing required field
                    if field_name in properties:
                        field_schema = properties[field_name]
                        # Resolve $ref if present
                        if '$ref' in field_schema:
                            try:
                                field_schema = self.parser.resolve_ref(field_schema['$ref'])
                            except (ValueError, KeyError):
                                pass
                        valid_payload[field_name] = self._get_default_value(field_schema, field_name)
       
        # Fix invalid enum values
        for field_name, field_value in valid_payload.items():
            if field_name in properties and not (field_name.startswith('**') and field_name.endswith('**')):
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
                        valid_payload[field_name] = 'available'
                    elif len(enum_values) > 0:
                        valid_payload[field_name] = enum_values[0]
       
        return valid_payload
   
    def _validate_and_fix_payload_fields(self, endpoint: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that payload uses correct field names from schema.
        If LLM generated wrong field names, replace the entire payload with correct one.
        """
        # Get the request body schema
        request_body = endpoint.get('request_body', {})
        if not request_body:
            return payload
        
        content = request_body.get('content', {})
        schema = None
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
        schema_field_names = set(properties.keys())
        payload_field_names = set(payload.keys())
        
        # Remove metadata fields from comparison
        payload_field_names = {k for k in payload_field_names if not (k.startswith('**') and k.endswith('**'))}
        
        # Check if payload has any fields that don't exist in schema
        invalid_fields = payload_field_names - schema_field_names
        
        # If payload has wrong fields, check if it's completely wrong (like generic fields)
        common_generic_fields = {'id', 'name', 'description', 'status', 'title', 'content', 'value', 'type'}
        has_generic_fields = bool(payload_field_names & common_generic_fields)
        has_schema_fields = bool(payload_field_names & schema_field_names)
        
        # If payload has generic fields but no schema fields, or has many invalid fields, replace it
        if (has_generic_fields and not has_schema_fields) or (len(invalid_fields) > 0 and len(invalid_fields) >= len(payload_field_names) / 2):
            logger.warning(f"LLM generated payload with wrong field names: {payload_field_names}. Schema has: {schema_field_names}. Replacing with correct payload.")
            # Generate a new payload using the correct schema
            return self._generate_sample_payload(endpoint)
        
        # If some fields are wrong but some are correct, just remove the wrong ones
        if invalid_fields:
            logger.warning(f"Removing invalid fields from payload: {invalid_fields}. Schema has: {schema_field_names}")
            valid_payload = {k: v for k, v in payload.items() if k in schema_field_names or (k.startswith('**') and k.endswith('**'))}
            return valid_payload
        
        return payload
   
    def _generate_sample_payload(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate sample payload from endpoint schema."""
        payload = {}
        method = endpoint.get('method', 'GET').upper()
       
        # Extract path parameters from endpoint path (they should NOT be in payload)
        path = endpoint.get('path', '')
        path_params = set(re.findall(r'{(\w+)}', path))
       
        # Detect content type and parameters
        content_info = self._detect_content_type(endpoint)
       
        # For GET/DELETE methods, use query parameters
        if method in ['GET', 'DELETE']:
            # Add query parameters
            for param_name, param_info in content_info['query_params'].items():
                # Explicit handling for enum-based query params (including array enums)
                schema = param_info.get('schema', {}) or {}
                param_type = param_info.get('type') or schema.get('type')
                # If this is an array of enums (e.g., status array with enum values)
                if schema.get('type') == 'array':
                    items_schema = schema.get('items', {}) or {}
                    enum_values = items_schema.get('enum') or []
                    if enum_values:
                        # Prefer "available" / "pending" when present, otherwise first enum
                        preferred = None
                        for candidate in ['available', 'pending']:
                            if candidate in enum_values:
                                preferred = candidate
                                break
                        if preferred is None:
                            preferred = enum_values[0]
                        # For array query params, always send at least one valid value
                        payload[param_name] = [preferred]
                        continue
                # If this is a simple enum (non‑array) on the parameter itself
                enum_values_direct = param_info.get('enum') or schema.get('enum')
                if enum_values_direct:
                    preferred = None
                    for candidate in ['available', 'pending']:
                        if candidate in enum_values_direct:
                            preferred = candidate
                            break
                    if preferred is None:
                        preferred = enum_values_direct[0]
                    payload[param_name] = preferred
                    continue
                # Fall back to explicit default if provided
                if param_info.get('default') is not None:
                    payload[param_name] = param_info['default']
                # Required param with no enum/default – use schema‑aware default
                elif param_info.get('required', False):
                    payload[param_name] = self._get_default_value(schema, param_name)
            return payload
       
        # For POST/PUT/PATCH, generate request body payload
        if content_info['is_form_data'] or content_info['is_multipart']:
            # Generate form parameters - ALWAYS include required ones
            for param_name, param_info in content_info['form_params'].items():
                param_schema = param_info.get('schema', {})
               
                if param_info['type'] == 'file':
                    # For file parameters, we'll mark them specially
                    payload[param_name] = '**FILE**'
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
            payload['**content_type**'] = content_info['content_type']
            payload['**is_multipart**'] = content_info['is_multipart']
            payload['**is_form_data**'] = content_info['is_form_data']
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
                status_value = 'available' # Default
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
        # For GET/DELETE, query params were already handled above, so skip them here
        if method not in ['GET', 'DELETE']:
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
                    # Resolve $ref if present
                    if '$ref' in param_schema:
                        try:
                            param_schema = self.parser.resolve_ref(param_schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    
                    default = param_schema.get('default')
                    if default is not None:
                        payload[param_name] = default
                    elif param.get('required', False):
                        # For array query params with enum items, generate proper array
                        if param_schema.get('type') == 'array':
                            items_schema = param_schema.get('items', {})
                            if '$ref' in items_schema:
                                try:
                                    items_schema = self.parser.resolve_ref(items_schema['$ref'])
                                except (ValueError, KeyError):
                                    pass
                            enum_values = items_schema.get('enum', [])
                            if enum_values:
                                # Prefer "available" / "pending" when present
                                preferred = None
                                for candidate in ['available', 'pending']:
                                    if candidate in enum_values:
                                        preferred = candidate
                                        break
                                if preferred is None:
                                    preferred = enum_values[0]
                                payload[param_name] = [preferred]
                            else:
                                payload[param_name] = []
                        else:
                            payload[param_name] = self._get_default_value(param_schema, param_name)
       
        return payload
   
    def _generate_complete_payload_for_put(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete payload for PUT requests (PUT replaces entire resource)."""
        path = endpoint.get('path', '')
        operation_id = endpoint.get('operation_id', '')
       
        # Generate comprehensive payload based on resource type
        if 'pet' in path.lower() or 'pet' in operation_id.lower():
            # Try to get the actual schema to use proper enum values
            request_body = endpoint.get('request_body', {})
            status_value = 'available' # Default
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
   
    def _generate_from_schema(self, schema: Dict[str, Any], field_name: Optional[str] = None) -> Any:
        """Generate sample value from JSON schema, properly resolving $ref references."""
        # Resolve $ref if present
        if '$ref' in schema:
            try:
                resolved_schema = self.parser.resolve_ref(schema['$ref'])
                # Recursively generate from resolved schema
                return self._generate_from_schema(resolved_schema, field_name)
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
                    result[prop_name] = self._get_default_value(prop_schema, prop_name)
           
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
                        result[prop_name] = self._get_default_value(prop_schema, prop_name)
                    # Include nested objects even if optional (for completeness)
                    elif prop_schema.get('type') == 'object':
                        nested_result = self._generate_from_schema(prop_schema, prop_name)
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
            return [self._get_default_value(items, field_name)]
        else:
            return self._get_default_value(schema, field_name)
   
    def _resolve_schema_refs(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve all $ref references in a schema."""
        if not isinstance(schema, dict):
            return schema
        
        # If this is a $ref, resolve it
        if '$ref' in schema:
            try:
                resolved = self.parser.resolve_ref(schema['$ref'])
                # Recursively resolve refs in the resolved schema
                return self._resolve_schema_refs(resolved)
            except (ValueError, KeyError) as e:
                logger.warning(f"Could not resolve $ref {schema.get('$ref')}: {e}")
                return schema
        
        # Create a copy to avoid modifying the original
        resolved = {}
        for key, value in schema.items():
            if key == 'properties' and isinstance(value, dict):
                # Resolve refs in properties
                resolved[key] = {}
                for prop_name, prop_schema in value.items():
                    resolved[key][prop_name] = self._resolve_schema_refs(prop_schema)
            elif key == 'items' and isinstance(value, dict):
                # Resolve refs in array items
                resolved[key] = self._resolve_schema_refs(value)
            elif key == 'allOf' and isinstance(value, list):
                # Resolve refs in allOf
                resolved[key] = [self._resolve_schema_refs(item) for item in value]
            elif key == 'oneOf' and isinstance(value, list):
                # Resolve refs in oneOf
                resolved[key] = [self._resolve_schema_refs(item) for item in value]
            elif key == 'anyOf' and isinstance(value, list):
                # Resolve refs in anyOf
                resolved[key] = [self._resolve_schema_refs(item) for item in value]
            elif isinstance(value, dict):
                # Recursively resolve nested objects
                resolved[key] = self._resolve_schema_refs(value)
            elif isinstance(value, list):
                # Resolve refs in list items
                resolved[key] = [self._resolve_schema_refs(item) if isinstance(item, dict) else item for item in value]
            else:
                resolved[key] = value
        
        return resolved
   
    def _get_default_value(self, schema: Dict[str, Any], field_name: Optional[str] = None) -> Any:
        """Get default value for schema type using Faker for realistic data generation."""
        schema_type = schema.get('type')
        default = schema.get('default')
        format_type = schema.get('format', '')
       
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
            # Use field name and format to determine appropriate Faker method
            field_lower = (field_name or '').lower()
            
            # Format-based generation
            if format_type == 'email' or 'email' in field_lower:
                return self.faker.email()
            elif format_type == 'date' or 'date' in field_lower:
                return self.faker.date().isoformat()
            elif format_type == 'date-time' or 'datetime' in field_lower or 'timestamp' in field_lower:
                return self.faker.iso8601()
            elif format_type == 'uri' or 'url' in field_lower:
                return self.faker.url()
            elif format_type == 'uuid' or 'uuid' in field_lower or field_lower.endswith('_id'):
                return str(self.faker.uuid4())
            elif format_type == 'ipv4' or 'ip' in field_lower:
                return self.faker.ipv4()
            elif format_type == 'ipv6':
                return self.faker.ipv6()
            elif format_type == 'hostname':
                return self.faker.domain_name()
            
            # Field name-based generation
            elif 'name' in field_lower:
                if 'first' in field_lower:
                    return self.faker.first_name()
                elif 'last' in field_lower:
                    return self.faker.last_name()
                elif 'full' in field_lower or 'user' in field_lower:
                    return self.faker.name()
                else:
                    return self.faker.word().capitalize()
            elif 'phone' in field_lower or 'mobile' in field_lower:
                return self.faker.phone_number()
            elif 'address' in field_lower:
                if 'street' in field_lower or 'line' in field_lower:
                    return self.faker.street_address()
                elif 'city' in field_lower:
                    return self.faker.city()
                elif 'state' in field_lower or 'province' in field_lower:
                    return self.faker.state()
                elif 'zip' in field_lower or 'postal' in field_lower:
                    return self.faker.zipcode()
                elif 'country' in field_lower:
                    return self.faker.country()
                else:
                    return self.faker.address()
            elif 'company' in field_lower or 'organization' in field_lower:
                return self.faker.company()
            elif 'title' in field_lower or 'subject' in field_lower:
                return self.faker.sentence(nb_words=4)
            elif 'description' in field_lower or 'bio' in field_lower or 'about' in field_lower:
                return self.faker.text(max_nb_chars=200)
            elif 'password' in field_lower:
                return self.faker.password(length=12)
            elif 'username' in field_lower or 'user' in field_lower:
                return self.faker.user_name()
            elif 'token' in field_lower or 'api_key' in field_lower:
                return self.faker.sha256()
            elif 'color' in field_lower:
                return self.faker.color_name()
            elif 'website' in field_lower or 'url' in field_lower:
                return self.faker.url()
            elif 'image' in field_lower or 'photo' in field_lower or 'avatar' in field_lower:
                return self.faker.image_url()
            elif 'price' in field_lower or 'cost' in field_lower or 'amount' in field_lower:
                return f"{self.faker.random_int(min=1, max=1000)}.{self.faker.random_int(min=10, max=99)}"
            elif 'code' in field_lower:
                if 'postal' in field_lower or 'zip' in field_lower:
                    return self.faker.zipcode()
                else:
                    return self.faker.bothify(text='??###')
            elif 'status' in field_lower:
                return random.choice(['active', 'inactive', 'pending'])
            elif 'category' in field_lower or 'tag' in field_lower:
                return self.faker.word()
            elif 'comment' in field_lower or 'message' in field_lower or 'note' in field_lower:
                return self.faker.sentence()
            else:
                # Default: generate a realistic word or sentence based on minLength/maxLength
                min_length = schema.get('minLength', 0)
                max_length = schema.get('maxLength', 100)
                if max_length > 50:
                    return self.faker.sentence(nb_words=min(10, max_length // 10))
                else:
                    return self.faker.word()[:max_length] if max_length > 0 else self.faker.word()
        elif schema_type == 'integer':
            # Use field name to determine appropriate integer generation
            field_lower = (field_name or '').lower()
            
            if 'id' in field_lower:
                # For IDs, generate positive integers
                minimum = schema.get('minimum', 1)
                maximum = schema.get('maximum', 1000000)
                return self.faker.random_int(min=max(1, minimum), max=max(1, maximum))
            elif 'age' in field_lower:
                return self.faker.random_int(min=18, max=100)
            elif 'count' in field_lower or 'quantity' in field_lower or 'qty' in field_lower:
                minimum = schema.get('minimum', 1)
                maximum = schema.get('maximum', 100)
                return self.faker.random_int(min=max(1, minimum), max=max(1, maximum))
            elif 'year' in field_lower:
                return self.faker.year()
            elif 'month' in field_lower:
                return self.faker.month()
            elif 'day' in field_lower:
                return self.faker.day_of_month()
            else:
                minimum = schema.get('minimum', 1)
                maximum = schema.get('maximum', 1000)
                return self.faker.random_int(min=max(1, minimum), max=max(1, maximum))
        elif schema_type == 'number':
            # Use field name to determine appropriate number generation
            field_lower = (field_name or '').lower()
            
            if 'price' in field_lower or 'cost' in field_lower or 'amount' in field_lower or 'total' in field_lower:
                minimum = schema.get('minimum', 0.01)
                maximum = schema.get('maximum', 10000.0)
                return round(self.faker.pyfloat(left_digits=4, right_digits=2, positive=True, min_value=minimum, max_value=maximum), 2)
            elif 'rate' in field_lower or 'percentage' in field_lower or 'percent' in field_lower:
                return round(self.faker.pyfloat(left_digits=1, right_digits=2, positive=True, min_value=0, max_value=100), 2)
            elif 'latitude' in field_lower:
                return self.faker.latitude()
            elif 'longitude' in field_lower:
                return self.faker.longitude()
            else:
                minimum = schema.get('minimum', 0.0)
                maximum = schema.get('maximum', 1000.0)
                return self.faker.pyfloat(left_digits=3, right_digits=2, positive=True, min_value=minimum, max_value=maximum)
        elif schema_type == 'boolean':
            return self.faker.boolean()
        elif schema_type == 'array':
            # For arrays, check if items have enum values
            items = schema.get('items', {})
            if '$ref' in items:
                try:
                    items = self.parser.resolve_ref(items['$ref'])
                except (ValueError, KeyError):
                    pass
            enum_values = items.get('enum', [])
            if enum_values:
                # Return array with one enum value (prefer "available" or "pending")
                preferred = None
                for candidate in ['available', 'pending']:
                    if candidate in enum_values:
                        preferred = candidate
                        break
                if preferred is None:
                    preferred = enum_values[0]
                return [preferred]
            # Generate array with 1-3 items
            min_items = schema.get('minItems', 1)
            max_items = schema.get('maxItems', 3)
            array_size = self.faker.random_int(min=min_items, max=max_items)
            items_schema = schema.get('items', {})
            return [self._get_default_value(items_schema, field_name) for _ in range(array_size)]
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
                    payload[key] = 12345 # Wrong type - string field gets number
                elif isinstance(value, int):
                    payload[key] = "invalid_string" # Wrong type - number field gets string
                elif isinstance(value, bool):
                    payload[key] = "not_boolean" # Wrong type - boolean field gets string
                elif isinstance(value, list):
                    payload[key] = "not_an_array" # Wrong type - array field gets string
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
                    payload[key] = "a" * 1000 # Reasonable long string (reduced from 10000)
                elif isinstance(payload[key], dict):
                    for nested_key in payload[key]:
                        if isinstance(payload[key][nested_key], str):
                            payload[key][nested_key] = "a" * 1000
        elif boundary_type == 'min_length':
            for key in payload:
                if isinstance(payload[key], str):
                    payload[key] = "a" # Single character
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
                            payload[key] = payload_value # This violates enum constraint
                        # Violate format constraints - inject attack vector into formatted fields
                        elif prop_format and prop_type == 'string':
                            payload[key] = payload_value # Violates format (email, date, uri, etc.)
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
                payload[key] = "x" * 1000 # 1KB string (reduced from 10KB to avoid 500 errors)
            elif isinstance(payload[key], list):
                payload[key] = [{"item": i} for i in range(100)] # Moderate array (reduced from 1000)
            elif isinstance(payload[key], dict):
                # Expand nested objects
                for i in range(10):
                    payload[key][f'field*{i}'] = "x" * 100
       
        return payload
   
    def _find_related_endpoints(self, endpoint: Dict[str, Any], all_endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Find related endpoints that can be chained together, including rollback operations.
        
        Args:
            endpoint: Current endpoint being analyzed
            all_endpoints: List of all endpoints in the OpenAPI spec
            
        Returns:
            Dictionary with related endpoints (create, update, delete, get) and rollback info
        """
        endpoint_path = endpoint.get('path', '')
        endpoint_method = endpoint.get('method', '').upper()
        
        # Extract resource name from path (e.g., /api/pets/{petId} -> pets)
        resource_match = re.search(r'/([^/]+)(?:/\{[^}]+\})?/?$', endpoint_path)
        resource_name = resource_match.group(1) if resource_match else None
        
        related = {
            'create': None,
            'get': None,
            'update': None,
            'delete': None,
            'list': None,
            'rollback_operations': []
        }
        
        if not resource_name:
            return related
        
        # Find related endpoints for the same resource
        for ep in all_endpoints:
            ep_path = ep.get('path', '')
            ep_method = ep.get('method', '').upper()
            
            # Skip the current endpoint
            if ep_path == endpoint_path and ep_method == endpoint_method:
                continue
            
            # Check if this endpoint is related to the same resource
            if resource_name in ep_path:
                if ep_method == 'POST' and '{' not in ep_path:
                    related['create'] = ep
                elif ep_method == 'GET' and '{' in ep_path:
                    related['get'] = ep
                elif ep_method == 'GET' and '{' not in ep_path:
                    related['list'] = ep
                elif ep_method in ['PUT', 'PATCH'] and '{' in ep_path:
                    related['update'] = ep
                elif ep_method == 'DELETE' and '{' in ep_path:
                    related['delete'] = ep
        
        # Determine rollback operations based on endpoint type
        if endpoint_method == 'POST' and related['delete']:
            # If creating, rollback is to delete
            related['rollback_operations'].append({
                'endpoint': related['delete']['path'],
                'method': 'DELETE',
                'description': f"Rollback: Delete created {resource_name}"
            })
        elif endpoint_method in ['PUT', 'PATCH'] and related['update']:
            # If updating, rollback is to restore previous state (would need to store original)
            # For now, we'll note that rollback requires storing original state
            related['rollback_operations'].append({
                'endpoint': related['update']['path'],
                'method': endpoint_method,
                'description': f"Rollback: Restore previous {resource_name} state",
                'requires_original_state': True
            })
        elif endpoint_method == 'DELETE':
            # If deleting, rollback is to recreate (would need to store original data)
            if related['create']:
                related['rollback_operations'].append({
                    'endpoint': related['create']['path'],
                    'method': 'POST',
                    'description': f"Rollback: Recreate deleted {resource_name}",
                    'requires_original_data': True
                })
        
        return related
    
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
               
                # Check for array type and collection format
                is_array = param_type == 'array'
                collection_format = param.get('collectionFormat', 'csv') # csv, ssv, tsv, pipes, multi
                explode = param.get('explode', False)
                style = param.get('style', 'form') # form, spaceDelimited, pipeDelimited, deepObject
               
                # Get array items info if array
                array_items = None
                if is_array:
                    array_items = param_schema.get('items', {})
                    if '$ref' in array_items:
                        try:
                            array_items = self.parser.resolve_ref(array_items['$ref'])
                        except (ValueError, KeyError):
                            pass
                    array_item_type = array_items.get('type', 'string') if array_items else 'string'
                    array_item_enum = array_items.get('enum') if array_items else None
               
                param_desc = f" - {param_name} ({param_in}"
                if param_required:
                    param_desc += ", REQUIRED"
                param_desc += f", type: {param_type}"
               
                if is_array:
                    param_desc += f", array of {array_item_type if array_items else 'unknown'}"
                    if array_item_enum:
                        param_desc += f", Allowed values (enum): {array_item_enum} (exact case, no extras)"
                    # Collection format is critical for query arrays
                    if param_in == 'query':
                        if collection_format == 'multi' or explode:
                            param_desc += f", Collection format: multi (e.g., ?{param_name}=value1&{param_name}=value2)"
                        elif collection_format == 'csv':
                            param_desc += f", Collection format: csv (e.g., ?{param_name}=value1,value2)"
                        elif collection_format == 'ssv':
                            param_desc += f", Collection format: ssv (e.g., ?{param_name}=value1 value2)"
                        elif collection_format == 'pipes':
                            param_desc += f", Collection format: pipes (e.g., ?{param_name}=value1|value2)"
                        else:
                            param_desc += f", Collection format: {collection_format}"
               
                if param_enum and not is_array:
                    param_desc += f", Allowed values (enum): {param_enum} (exact case, no extras)"
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
                context_parts.append(f" Content-Type: {content_type}")
               
                # Resolve $ref if present
                if '$ref' in schema:
                    ref_name = schema['$ref'].split('/')[-1]
                    context_parts.append(f" Schema Reference: {ref_name}")
                    try:
                        resolved_schema = self.parser.resolve_ref(schema['$ref'])
                        schema = resolved_schema
                        context_parts.append(f" (Resolved schema details below)")
                    except (ValueError, KeyError) as e:
                        context_parts.append(f" (Could not resolve: {e})")
               
                # Add detailed schema information
                schema_type = schema.get('type', 'unknown')
                context_parts.append(f" Schema type: {schema_type}")
               
                if schema_type == 'object':
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                   
                    if required:
                        context_parts.append(f" REQUIRED FIELDS (must be included): {', '.join(required)}")
                   
                    if properties:
                        context_parts.append(f" Properties:")
                        for prop_name, prop_schema in list(properties.items())[:15]: # Limit to first 15
                            # Resolve $ref in property if present
                            if '$ref' in prop_schema:
                                try:
                                    prop_schema = self.parser.resolve_ref(prop_schema['$ref'])
                                except (ValueError, KeyError):
                                    pass
                           
                            prop_type = prop_schema.get('type', 'unknown')
                            prop_desc = f" - {prop_name}: {prop_type}"
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
                context_parts.append(f" - {status}: {response_info.get('description', 'N/A')}")
       
        return "\n".join(context_parts)
   
    def _create_test_generation_prompt(self, endpoint: Dict[str, Any], context: str) -> str:
        """Create prompt for LLM test generation."""
        # Prepare endpoint details for the prompt
        endpoint_path = endpoint.get('path', 'N/A')
        endpoint_method = endpoint.get('method', 'N/A')
        endpoint_summary = endpoint.get('summary', endpoint.get('description', 'N/A'))
        
        # Format parameters
        parameters = endpoint.get('parameters', [])
        parameters_json = json.dumps(parameters, indent=2) if parameters else "[]"
        
        # Format request body - resolve $ref references first
        request_body = endpoint.get('request_body', {})
        if request_body:
            # Create a copy to avoid modifying the original
            resolved_request_body = {}
            if 'content' in request_body:
                resolved_request_body['content'] = {}
                for content_type, schema_info in request_body['content'].items():
                    schema = schema_info.get('schema', {})
                    # Resolve $ref if present
                    if '$ref' in schema:
                        try:
                            resolved_schema = self.parser.resolve_ref(schema['$ref'])
                            resolved_request_body['content'][content_type] = {
                                'schema': resolved_schema
                            }
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Could not resolve $ref in request body: {e}")
                            # Fallback to original schema
                            resolved_request_body['content'][content_type] = schema_info
                    else:
                        # Recursively resolve $ref in nested schemas (including array items)
                        resolved_schema = self._resolve_schema_refs(schema)
                        resolved_request_body['content'][content_type] = {
                            'schema': resolved_schema
                        }
            else:
                resolved_request_body = request_body
            request_body_json = json.dumps(resolved_request_body, indent=2)
        else:
            request_body_json = "{}"
        
        # Format responses
        responses = endpoint.get('responses', {})
        responses_json = json.dumps(responses, indent=2) if responses else "{}"
        
        # Detect query array enums that need multiple variants
        query_array_enum_instructions = ""
        if parameters:
            for param in parameters:
                if param.get('in') == 'query':
                    param_schema = param.get('schema', {})
                    if '$ref' in param_schema:
                        try:
                            param_schema = self.parser.resolve_ref(param_schema['$ref'])
                        except (ValueError, KeyError):
                            pass
                    
                    if param_schema.get('type') == 'array':
                        items = param_schema.get('items', {})
                        if '$ref' in items:
                            try:
                                items = self.parser.resolve_ref(items['$ref'])
                            except (ValueError, KeyError):
                                pass
                        
                        enum_values = items.get('enum') if items else None
                        collection_format = param.get('collectionFormat', 'csv')
                        explode = param.get('explode', False)
                        param_required = param.get('required', False)
                        
                        if enum_values and (collection_format == 'multi' or explode):
                            num_values = len(enum_values)
                            single_tests = num_values
                            pair_tests = num_values * (num_values - 1) // 2 if num_values > 1 else 0
                            all_combined = 1 if num_values > 1 else 0
                            total_happy_paths = single_tests + pair_tests + all_combined
                            
                            query_array_enum_instructions += f"""
CRITICAL: Parameter '{param.get('name')}' is a query array with enum values: {enum_values}
Collection format: multi (repeated query parameters like ?status=available&status=pending)

YOU MUST generate EXACTLY {total_happy_paths} SEPARATE happy_path test cases for this parameter:
1. {single_tests} single-value tests (one per enum value):
"""
                            for i, val in enumerate(enum_values, 1):
                                query_array_enum_instructions += f"   - Test {i}: {{'type': 'happy_path', 'name': 'Query with {param.get('name')}={val}', 'payload': {{'{param.get('name')}': ['{val}']}}, 'expected_status': [200]}}\n"
                            
                            if pair_tests > 0:
                                query_array_enum_instructions += f"\n2. {pair_tests} pair combination tests (all pairs):\n"
                                pair_num = single_tests + 1
                                for i, val1 in enumerate(enum_values):
                                    for val2 in enum_values[i+1:]:
                                        query_array_enum_instructions += f"   - Test {pair_num}: {{'type': 'happy_path', 'name': 'Query with {param.get('name')}={val1} and {param.get('name')}={val2}', 'payload': {{'{param.get('name')}': ['{val1}', '{val2}']}}, 'expected_status': [200]}}\n"
                                        pair_num += 1
                            
                            if all_combined > 0:
                                enum_list_str = "[" + ", ".join([f"'{v}'" for v in enum_values]) + "]"
                                query_array_enum_instructions += f"\n3. 1 all-values-combined test:\n"
                                query_array_enum_instructions += f"   - Test {total_happy_paths}: {{'type': 'happy_path', 'name': 'Query with all {param.get('name')} values', 'payload': {{'{param.get('name')}': {enum_list_str}}}, 'expected_status': [200]}}\n"
                            
                            query_array_enum_instructions += f"\nEach of these {total_happy_paths} tests MUST be a SEPARATE entry in your JSON array. DO NOT combine them.\n"
        
        # Extract exact property names from resolved request body schema
        exact_property_names = []
        exact_property_details = []
        item_schema_for_example = None  # Store resolved item schema for array types
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
                    
                    # Handle array schemas with items.$ref
                    if schema.get('type') == 'array':
                        items = schema.get('items', {})
                        if isinstance(items, dict):
                            # Resolve $ref in items if present
                            if '$ref' in items:
                                try:
                                    items = self.parser.resolve_ref(items['$ref'])
                                    item_schema_for_example = items  # Store for example generation
                                except (ValueError, KeyError):
                                    pass
                            
                            # Extract properties from the item schema
                            if items.get('type') == 'object':
                                properties = items.get('properties', {})
                                required = items.get('required', [])
                                
                                for prop_name, prop_schema in properties.items():
                                    exact_property_names.append(prop_name)
                                    prop_type = prop_schema.get('type', 'unknown')
                                    prop_desc = f"  - {prop_name} ({prop_type}"
                                    if prop_name in required:
                                        prop_desc += ", REQUIRED"
                                    if prop_schema.get('enum'):
                                        prop_desc += f", enum: {prop_schema.get('enum')}"
                                    if prop_schema.get('format'):
                                        prop_desc += f", format: {prop_schema.get('format')}"
                                    prop_desc += ")"
                                    exact_property_details.append(prop_desc)
                    
                    # Handle object schemas
                    elif schema.get('type') == 'object':
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        
                        for prop_name, prop_schema in properties.items():
                            exact_property_names.append(prop_name)
                            prop_type = prop_schema.get('type', 'unknown')
                            prop_desc = f"  - {prop_name} ({prop_type}"
                            if prop_name in required:
                                prop_desc += ", REQUIRED"
                            if prop_schema.get('enum'):
                                prop_desc += f", enum: {prop_schema.get('enum')}"
                            if prop_schema.get('format'):
                                prop_desc += f", format: {prop_schema.get('format')}"
                            prop_desc += ")"
                            exact_property_details.append(prop_desc)
                    break
        
        # Build explicit schema instructions with concrete example
        schema_instructions = ""
        is_array_schema = False
        if exact_property_names:
            # Get properties dict for creating example
            properties = {}
            if request_body:
                content = request_body.get('content', {})
                for content_type, schema_info in content.items():
                    if 'application/json' in content_type:
                        schema = schema_info.get('schema', {})
                        if '$ref' in schema:
                            try:
                                schema = self.parser.resolve_ref(schema['$ref'])
                            except (ValueError, KeyError):
                                pass
                        
                        # Check if it's an array schema
                        if schema.get('type') == 'array':
                            is_array_schema = True
                            items = schema.get('items', {})
                            if isinstance(items, dict):
                                if '$ref' in items:
                                    try:
                                        items = self.parser.resolve_ref(items['$ref'])
                                    except (ValueError, KeyError):
                                        pass
                                if items.get('type') == 'object':
                                    properties = items.get('properties', {})
                        elif schema.get('type') == 'object':
                            properties = schema.get('properties', {})
                        break
            
            # Create a concrete example payload using the exact field names
            if is_array_schema:
                # For array schemas, create an array with one item
                example_item = {}
                for prop_name in exact_property_names:
                    prop_schema = properties.get(prop_name, {})
                    prop_type = prop_schema.get('type', 'string')
                    if prop_type == 'integer':
                        example_item[prop_name] = 0
                    elif prop_type == 'number':
                        example_item[prop_name] = 0.0
                    elif prop_type == 'boolean':
                        example_item[prop_name] = True
                    elif prop_type == 'array':
                        example_item[prop_name] = []
                    else:
                        example_item[prop_name] = "string"
                example_payload = [example_item]  # Array with one item
            else:
                # For object schemas, create a single object
                example_payload = {}
                for prop_name in exact_property_names:
                    prop_schema = properties.get(prop_name, {})
                    prop_type = prop_schema.get('type', 'string')
                    if prop_type == 'integer':
                        example_payload[prop_name] = 0
                    elif prop_type == 'number':
                        example_payload[prop_name] = 0.0
                    elif prop_type == 'boolean':
                        example_payload[prop_name] = True
                    elif prop_type == 'array':
                        example_payload[prop_name] = []
                    else:
                        example_payload[prop_name] = "string"
            
            example_json = json.dumps(example_payload, indent=2)
            
            array_note = ""
            if is_array_schema:
                array_note = "\n⚠️  IMPORTANT: This endpoint expects an ARRAY of objects. Each object in the array must use ONLY the fields listed above.\n"
            
            schema_instructions = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CRITICAL REQUEST BODY SCHEMA REQUIREMENTS                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

⚠️  MANDATORY: You MUST use EXACTLY these property names (case-sensitive):
{chr(10).join(exact_property_details)}
{array_note}
✅ CORRECT payload format (copy this structure):
{example_json}

❌ FORBIDDEN - DO NOT USE these generic field names:
  - "id", "name", "description", "status", "title", "content", "value", "type"
  - UNLESS they appear in the exact property list above

🚫 ABSOLUTELY FORBIDDEN:
  - DO NOT invent field names
  - DO NOT use similar-sounding names (e.g., "talukaId" ≠ "id")
  - DO NOT use generic placeholder names
  - DO NOT guess what fields might exist

✅ REQUIRED ACTIONS:
  1. Look at the "Request Body Schema" section below
  2. For array schemas: Find the "items" → "$ref" → resolved schema → "properties" object
  3. For object schemas: Find the "properties" object directly
  4. Use ONLY the field names listed in the properties
  5. For happy_path tests, include ALL required fields
  6. Use appropriate data types (integer, string, etc.) as specified
  7. For array endpoints: Generate an array with 1-3 items, each using ONLY the schema fields

📋 EXACT FIELD NAMES TO USE: {', '.join(exact_property_names)}

If you generate payloads with wrong field names, they will be REJECTED and replaced.
Generate payloads using ONLY the field names listed above.

"""
        
        # Check if this is a DELETE or PUT/PATCH endpoint with path parameters
        has_path_params = bool(re.search(r'\{(\w+)\}', endpoint_path))
        is_delete = endpoint_method.upper() == 'DELETE'
        is_put_patch = endpoint_method.upper() in ['PUT', 'PATCH']
        needs_create_first = (is_delete or is_put_patch) and has_path_params
        
        # Find related endpoints for chained API and rollback
        chained_api_instructions = ""
        if hasattr(self, 'all_endpoints') and self.all_endpoints:
            related = self._find_related_endpoints(endpoint, self.all_endpoints)
            if related['rollback_operations'] or related['create'] or related['update'] or related['delete']:
                chained_api_instructions = "\n╔══════════════════════════════════════════════════════════════════════════════╗\n"
                chained_api_instructions += "║                    CHAINED API & ROLLBACK SUPPORT                              ║\n"
                chained_api_instructions += "╚══════════════════════════════════════════════════════════════════════════════╝\n\n"
                chained_api_instructions += "🔗 RELATED ENDPOINTS AVAILABLE FOR CHAINING:\n"
                if related['create']:
                    chained_api_instructions += f"  - CREATE: POST {related['create']['path']} ({related['create'].get('summary', 'N/A')})\n"
                if related['get']:
                    chained_api_instructions += f"  - GET: GET {related['get']['path']} ({related['get'].get('summary', 'N/A')})\n"
                if related['update']:
                    chained_api_instructions += f"  - UPDATE: {related['update']['method']} {related['update']['path']} ({related['update'].get('summary', 'N/A')})\n"
                if related['delete']:
                    chained_api_instructions += f"  - DELETE: DELETE {related['delete']['path']} ({related['delete'].get('summary', 'N/A')})\n"
                
                if related['rollback_operations']:
                    chained_api_instructions += "\n🔄 ROLLBACK OPERATIONS (if any step fails):\n"
                    for rollback_op in related['rollback_operations']:
                        chained_api_instructions += f"  - {rollback_op['method']} {rollback_op['endpoint']}: {rollback_op['description']}\n"
                        if rollback_op.get('requires_original_state') or rollback_op.get('requires_original_data'):
                            chained_api_instructions += f"    ⚠️  Note: This rollback requires storing original state/data\n"
                
                chained_api_instructions += "\n📋 CHAINED API TEST FORMAT:\n"
                chained_api_instructions += "For complex scenarios, you can generate chained API tests with rollback:\n"
                chained_api_instructions += "{\n"
                chained_api_instructions += '  "type": "e2e",\n'
                chained_api_instructions += '  "name": "Chained API test with rollback",\n'
                chained_api_instructions += '  "payload": {\n'
                chained_api_instructions += '    "flow": [\n'
                chained_api_instructions += '      {\n'
                chained_api_instructions += '        "endpoint": "/api/resource",\n'
                chained_api_instructions += '        "method": "POST",\n'
                chained_api_instructions += '        "payload": {...},\n'
                chained_api_instructions += '        "description": "Step 1: Create resource"\n'
                chained_api_instructions += '      },\n'
                chained_api_instructions += '      {\n'
                chained_api_instructions += '        "endpoint": "/api/resource/{id}",\n'
                chained_api_instructions += '        "method": "PUT",\n'
                chained_api_instructions += '        "payload": {...},\n'
                chained_api_instructions += '        "description": "Step 2: Update resource"\n'
                chained_api_instructions += '      }\n'
                chained_api_instructions += '    ],\n'
                chained_api_instructions += '    "rollback": [\n'
                chained_api_instructions += '      {\n'
                chained_api_instructions += '        "endpoint": "/api/resource/{id}",\n'
                chained_api_instructions += '        "method": "DELETE",\n'
                chained_api_instructions += '        "description": "Rollback: Delete if update fails"\n'
                chained_api_instructions += '      }\n'
                chained_api_instructions += '    ]\n'
                chained_api_instructions += '  },\n'
                chained_api_instructions += '  "expected_status": [200, 201],\n'
                chained_api_instructions += '  "description": "Chained API test with automatic rollback on failure"\n'
                chained_api_instructions += "}\n\n"
                chained_api_instructions += "⚠️  IMPORTANT: If any step in the flow fails, the rollback operations will be executed automatically.\n"
                chained_api_instructions += "   - Store IDs from create operations for use in subsequent steps\n"
                chained_api_instructions += "   - If a step fails, rollback will undo previous operations\n"
                chained_api_instructions += "   - Rollback operations use the same IDs/data from the failed flow\n"
        
        # Find the corresponding POST create endpoint if needed
        create_endpoint_info = ""
        create_path = ""
        multi_step_format_instructions = ""
        if needs_create_first:
            resource_match = re.match(r'^/([^/]+)', endpoint_path)
            if resource_match:
                resource = resource_match.group(1)
                # Look for a POST create endpoint for the same resource
                for ep in self.parser.get_endpoints():
                    if ep.get('method', '').upper() == 'POST':
                        ep_path = ep.get('path', '').rstrip('/')
                        if ep_path == f"/{resource}".rstrip('/') or ep_path == f"/{resource}s".rstrip('/'):
                            create_ep = ep
                            create_path = create_ep.get('path', '')
                            create_summary = create_ep.get('summary', create_ep.get('description', 'Create resource'))
                            action_word = "delete" if is_delete else "update"
                            Action_word = "Delete" if is_delete else "Update"
                            
                            create_endpoint_info = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MULTI-STEP TEST REQUIREMENT                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

⚠️  CRITICAL: This is a {endpoint_method} endpoint with path parameter(s) in the URL.
   You MUST generate tests that FIRST create the resource, THEN perform the {endpoint_method} operation.

   For happy_path tests, you MUST:
   1. First call POST {create_path} to create a resource and get a valid ID
   2. Then use that ID in the {endpoint_method} {endpoint_path} request

   Example for DELETE /store/order/{{orderId}}:
   - Step 1: POST /store/order (create order, get orderId from response)
   - Step 2: DELETE /store/order/{{orderId}} (use the orderId from step 1)

   Example for PUT /pet/{{petId}}:
   - Step 1: POST /pet (create pet, get petId from response)
   - Step 2: PUT /pet/{{petId}} (use the petId from step 1)

   Create endpoint details:
   - Path: {create_path}
   - Method: POST
   - Summary: {create_summary}
   
   ⚠️  CRITICAL REQUIREMENTS:
   1. For ALL happy_path tests for this {endpoint_method} endpoint, you MUST use multi-step format
   2. The first step MUST be POST {create_path} to create the resource
   3. The second step MUST use the ID from the first step's response in the path parameter
   4. The ID from step 1 response will be automatically extracted and used in step 2
   5. DO NOT generate single-step tests for this endpoint - they will fail without an ID
   
   Generate test cases that include BOTH steps in the flow.
   The payload for happy_path should include a "flow" array with both operations.
"""
                            
                            # Build multi-step format instructions (outside f-string to avoid backslash issues)
                            multi_step_format_instructions = f"""
   ⚠️  MANDATORY FOR DELETE/PUT/PATCH WITH PATH PARAMS - USE MULTI-STEP FORMAT:
   
   For ALL happy_path tests for this {endpoint_method} endpoint, you MUST use this format with 'flow' array:
   [
     {{
       "type": "happy_path",
       "name": "{Action_word} resource after creation",
       "payload": {{
         "flow": [
           {{
             "endpoint": "{create_path}",
             "method": "POST",
             "payload": {{...create payload with exact schema fields from POST endpoint...}},
             "description": "Step 1: Create resource to obtain ID"
           }},
           {{
             "endpoint": "{endpoint_path}",
             "method": "{endpoint_method}",
             "payload": {{...update/delete payload if needed (for PUT/PATCH include update fields)...}},
             "description": "Step 2: {Action_word} the created resource using ID from step 1"
           }}
         ]
       }},
       "expected_status": [200, 201, 204],
       "description": "Create resource then {action_word} it using the obtained ID"
     }}
   ]
   
   ⚠️  CRITICAL IMPLEMENTATION DETAILS:
   - Step 1 (POST): Create the resource. The response will contain an ID (e.g., {{"id": 123}} or {{"petId": 456}})
   - Step 2 ({endpoint_method}): Use the SAME ID from step 1's response in the path parameter
   - The system automatically extracts the ID from step 1's response and stores it in context
   - In step 2's endpoint, use placeholder format: {endpoint_path} (keep the {{id}} or {{username}} placeholder)
   - The system will automatically replace {{id}}/{{username}} with the actual ID from step 1
   - Example flow:
     * Step 1: POST /user → Response: {{"id": 123, "username": "john"}}
     * Step 2: DELETE /user/{{username}} → Becomes DELETE /user/john (using "john" from step 1)
   - For PUT/PATCH: Include the update payload in step 2 with fields to update (use exact schema field names)
   - For DELETE: Step 2 payload can be empty {{}} as DELETE typically doesn't need a body
   
   ✅ CORRECT FORMAT EXAMPLE:
   {{
     "type": "happy_path",
     "name": "Delete user after creation",
     "payload": {{
       "flow": [
         {{
           "endpoint": "/user",
           "method": "POST",
           "payload": {{"username": "testuser", "email": "test@example.com"}},
           "description": "Step 1: Create user to obtain ID"
         }},
         {{
           "endpoint": "/user/{{username}}",
           "method": "DELETE",
           "payload": {{}},
           "description": "Step 2: Delete the created user using username from step 1"
         }}
       ]
     }},
     "expected_status": [200, 201, 204],
     "description": "Create user then delete it using the obtained username"
   }}
   
   For other test types (negative, boundary, security), you can use standard single-step format below:
"""
                            break
        
        prompt = f"""
You are an expert API tester. Generate 10-15 DIVERSE and UNIQUE test cases for this endpoint from the OpenAPI spec.

IMPORTANT: Each test case must test a DIFFERENT scenario. NO duplicates or similar tests.

Endpoint Details:
- Path: {endpoint_path}
- Method: {endpoint_method}
- Summary: {endpoint_summary}

Parameters:
{parameters_json}

Request Body Schema (RESOLVED - $ref references have been expanded):
{request_body_json}

⚠️  CRITICAL: The schema above shows the EXACT structure. Look for the "properties" object.
   Each property name listed there MUST be used exactly as shown (case-sensitive).
   DO NOT use generic field names like "id", "name", "description" unless they appear in "properties".

{schema_instructions}

{create_endpoint_info}

Responses:
{responses_json}

{query_array_enum_instructions}

{chained_api_instructions}

Instructions:
1. Test Types to Cover (generate multiple variants of each):
   - happy_path: Valid schema-compliant inputs (expect 200/201)
     * For query array enums: Generate ALL variants as specified above
     * Include ALL required parameters/fields with valid types/enums/formats
     * Use EXACT property names from the Request Body Schema above - DO NOT invent names
     * Use different valid values for each happy_path test
     {"* For DELETE/PUT/PATCH with path params: MUST include create step first (see above)" if needs_create_first else ""}
   - negative: Missing required fields, invalid types/enums (expect 400/422)
     * One test per missing required parameter
     * One test per invalid enum value
     * One test per wrong data type
   - boundary: Min/max values, edge cases (expect 200/400/422 depending on validity)
   - security: SQL injection, XSS, invalid formats (expect 400/403)

2. Diversity Requirements:
   - For query array enums: Generate the EXACT number of happy_path variants as specified above
   - Use DIFFERENT valid values for each happy_path test (don't repeat the same payload)
   - Each test case must validate a UNIQUE scenario
   - Vary parameter values, combinations, and test conditions

3. Output Format:
{multi_step_format_instructions}
   Output as a JSON array of test objects:
   [
     {{
       "type": "happy_path",
       "name": "Descriptive unique test name",
       "payload": {{"fieldNameFromSchema": "value1", "anotherFieldFromSchema": 123}},
       "expected_status": [200],
       "description": "What this test validates"
     }},
     {{
       "type": "negative",
       "name": "Missing required parameter X",
       "payload": {{}},
       "expected_status": [400, 422],
       "description": "Test API rejects missing required field"
     }}
   ]
   
   ⚠️  CRITICAL: In the "payload" field, use ONLY field names from the Request Body Schema "properties" object.
   Example: If schema has "talukaId", "talukaName", "cityId", your payload MUST be:
   {{"talukaId": 0, "talukaName": "string", "cityId": 0}}
   
   DO NOT use: {{"id": 1, "name": "Test", "description": "Test"}} ❌ WRONG!

4. Critical Rules:
   - Generate max test cases total
   - Each test case must be UNIQUE (different payload, different scenario)
   - For query array enums: Generate ALL specified variants (single values + pairs + all combined)
   - NO duplicate test cases
   - NO similar test cases with only minor variations
   - Vary the test scenarios significantly
   - USE EXACT PROPERTY NAMES FROM THE SCHEMA - DO NOT INVENT NAMES

Generate the test cases now following ALL instructions above.
"""
        return prompt
   
    def _parse_llm_response(self, response: str, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse LLM response into test cases."""
        tests = []
       
        try:
            # Clean the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            
            # Remove markdown code block markers (```json ... ``` or ``` ... ```)
            if cleaned_response.startswith('```'):
                # Find the first newline after ```
                first_newline = cleaned_response.find('\n')
                if first_newline != -1:
                    cleaned_response = cleaned_response[first_newline+1:]
                # Remove trailing ```
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3].rstrip()
                elif cleaned_response.rstrip().endswith('```'):
                    cleaned_response = cleaned_response.rstrip()[:-3].rstrip()
            
            # Try to extract JSON array from response
            # First, try to find a complete JSON array
            json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if json_match:
                # If LLM didn't generate assertions, add them based on response schema
                expected_status = self._get_expected_status(endpoint)
                json_str = json_match.group()
                
                # Try to fix common JSON issues
                # Remove trailing commas before closing brackets/braces
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                
                # Try to parse the JSON
                try:
                    test_cases = json.loads(json_str)
                except json.JSONDecodeError as json_err:
                    # If JSON is incomplete, try to extract what we can
                    logger.warning(f"JSON parse error at position {json_err.pos}: {json_err.msg}")
                    logger.warning(f"JSON string around error: {json_str[max(0, json_err.pos-100):json_err.pos+100]}")
                    
                    # Try to find the last complete object in the array
                    # Look for complete objects ending with }
                    last_complete_pos = json_str.rfind('}')
                    if last_complete_pos != -1:
                        # Try to extract up to the last complete object
                        partial_json = json_str[:last_complete_pos+1]
                        # Try to close the array if needed
                        if not partial_json.rstrip().endswith(']'):
                            # Count opening and closing brackets
                            open_brackets = partial_json.count('[')
                            close_brackets = partial_json.count(']')
                            if open_brackets > close_brackets:
                                partial_json += ']'
                        
                        try:
                            test_cases = json.loads(partial_json)
                            logger.warning(f"Successfully parsed partial JSON with {len(test_cases)} test cases")
                        except json.JSONDecodeError:
                            # If still fails, try to extract individual objects
                            # Find all complete JSON objects
                            object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                            objects = re.findall(object_pattern, json_str, re.DOTALL)
                            if objects:
                                test_cases = []
                                for obj_str in objects:
                                    try:
                                        obj = json.loads(obj_str)
                                        test_cases.append(obj)
                                    except json.JSONDecodeError:
                                        continue
                                logger.warning(f"Extracted {len(test_cases)} test cases from individual objects")
                            else:
                                raise ValueError(f"Could not parse JSON: {json_err.msg} at position {json_err.pos}")
                    else:
                        raise ValueError(f"Could not parse JSON: {json_err.msg} at position {json_err.pos}")
                
                for test_case in test_cases:
                    test_type = test_case.get('type', 'happy_path')
                    
                    # Check if this is a multi-step test (has 'flow' in payload)
                    payload = test_case.get('payload', {})
                    if isinstance(payload, dict) and 'flow' in payload:
                        # This is a multi-step test (e.g., create then delete/update)
                        flow = payload.get('flow', [])
                        rollback = payload.get('rollback', [])
                        if flow and len(flow) >= 2:
                            # Convert to E2E format with rollback support
                            parsed_test = {
                                'type': TestType.E2E.value,
                                'endpoint': endpoint['path'],
                                'method': endpoint['method'].upper(),
                                'operation_id': endpoint['operation_id'],
                                'name': test_case.get('name', 'LLM Generated Multi-Step Test'),
                                'payload': {
                                    'flow': flow,
                                    'rollback': rollback if rollback else []
                                },
                                'expected_status': test_case.get('expected_status', [200, 201, 204]),
                                'description': test_case.get('description', ''),
                                'e2e_flow': flow
                            }
                            # Generate assertions for the final step
                            final_step = flow[-1]
                            final_method = final_step.get('method', endpoint['method'].upper())
                            expected_statuses = test_case.get('expected_status', [200, 201, 204])
                            generated_assertions = self._generate_assertions_from_responses(endpoint, expected_statuses)
                            if generated_assertions:
                                parsed_test['assertions'] = generated_assertions
                            tests.append(parsed_test)
                            continue
                    
                    # Standard single-step test
                    parsed_test = {
                        'type': test_type,
                        'endpoint': endpoint['path'],
                        'method': endpoint['method'].upper(),
                        'operation_id': endpoint['operation_id'],
                        'name': test_case.get('name', 'LLM Generated Test'),
                        'payload': payload,
                        'expected_status': test_case.get('expected_status', [200]),
                        'description': test_case.get('description', '')
                    }
                    
                    # Fix empty array enum values for GET/DELETE query parameters
                    if parsed_test['method'] in ['GET', 'DELETE']:
                        for param in endpoint.get('parameters', []):
                            if param.get('in') == 'query':
                                param_name = param.get('name')
                                param_schema = param.get('schema', {})
                                if '$ref' in param_schema:
                                    try:
                                        param_schema = self.parser.resolve_ref(param_schema['$ref'])
                                    except (ValueError, KeyError):
                                        pass
                                
                                # Check if this is an array enum parameter
                                if param_schema.get('type') == 'array':
                                    items_schema = param_schema.get('items', {})
                                    if '$ref' in items_schema:
                                        try:
                                            items_schema = self.parser.resolve_ref(items_schema['$ref'])
                                        except (ValueError, KeyError):
                                            pass
                                    
                                    enum_values = items_schema.get('enum', [])
                                    if enum_values:
                                        # Fix empty string or empty array values
                                        current_value = parsed_test['payload'].get(param_name)
                                        if current_value == "" or current_value == [] or current_value is None:
                                            # Prefer "available" / "pending" when present
                                            preferred = None
                                            for candidate in ['available', 'pending']:
                                                if candidate in enum_values:
                                                    preferred = candidate
                                                    break
                                            if preferred is None:
                                                preferred = enum_values[0]
                                            parsed_test['payload'][param_name] = [preferred]
                                            logger.info(f"Fixed empty array enum value for {param_name}, set to [{preferred}]")
                    
                    # For happy_path tests, ensure payload is schema-compliant
                    # BUT: Skip for GET/DELETE requests as they use query parameters, not request body
                    if test_type == 'happy_path' and parsed_test['method'] not in ['GET', 'DELETE']:
                        # First, validate that payload uses correct field names (replace if wrong)
                        validated_payload = self._validate_and_fix_payload_fields(
                            endpoint,
                            parsed_test['payload']
                        )
                        # Then ensure schema compliance (add missing required fields, fix enums)
                        parsed_test['payload'] = self._ensure_schema_compliance(
                            endpoint,
                            validated_payload,
                            ensure_required=True
                        )
                    # For GET/DELETE, preserve query parameters as-is (including arrays)
                    
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
                
                # Deduplicate tests based on payload and type
                seen_tests = set()
                unique_tests = []
                for test in tests:
                    # Create a unique key from type and payload
                    test_key = (
                        test.get('type', 'unknown'),
                        json.dumps(test.get('payload', {}), sort_keys=True)
                    )
                    if test_key not in seen_tests:
                        seen_tests.add(test_key)
                        unique_tests.append(test)
                    else:
                        logger.warning(f"Removed duplicate test: {test.get('name', 'unnamed')} with payload {test.get('payload', {})}")
                
                tests = unique_tests
                
                logger.info(f"Parsed {len(tests)} unique test cases from LLM response for endpoint {endpoint.get('path', 'unknown')}")
                # Log test types distribution
                test_types = {}
                for test in tests:
                    test_type = test.get('type', 'unknown')
                    test_types[test_type] = test_types.get(test_type, 0) + 1
                logger.info(f"Test types distribution: {test_types}")
            else:
                # No JSON array found in response
                raise ValueError(f"No valid JSON array found in LLM response. Response preview: {str(response)[:500]}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"LLM response was: {str(response)[:500]}")
            raise ValueError(f"LLM response is not valid JSON: {str(e)}. Response preview: {str(response)[:500]}")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {str(e)}", exc_info=True)
            logger.error(f"LLM response was: {str(response)[:500]}")
            raise ValueError(f"Failed to parse LLM response: {str(e)}")
        
        # Validate that we have tests
        if not tests or len(tests) == 0:
            raise ValueError(f"LLM returned no test cases. Response preview: {str(response)[:500]}")
        
        return tests
   
    def _generate_llm_tests(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate LLM-enhanced test cases using RAG."""
        if not self.llm_api_key:
            raise ValueError("LLM API key is required for LLM test generation")
        
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
                    raise ImportError("LangChain OpenAI not available. Please install langchain or langchain-openai package.")
            
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
            
            # Use temperature=0.9 for maximum diversity, max_tokens=4000 for longer outputs
            llm_kwargs = {
                "api_key": self.llm_api_key if self.llm_provider != "local" else "ollama",
                "model_name": self.llm_model,
                "openai_api_base": endpoint_url,
                "temperature": 0.9,  # High temperature for maximum diversity in test cases
                "max_tokens": 4000,  # Allow longer responses for 15-20 test cases
            }
            
            # Generate tests with explicit instruction to follow the prompt
            enhanced_prompt = f"""{prompt}

REMINDER: Generate ALL required test variants as specified above. Do not skip any test cases. Return ONLY valid JSON array."""
            
            # Log request details
            prompt_length = len(enhanced_prompt) if isinstance(enhanced_prompt, str) else len(str(enhanced_prompt))
            logger.info(
                "LLM request: provider=%s model=%s endpoint=%s prompt_length=%d chars, temperature=0.9, max_tokens=4000",
                self.llm_provider,
                self.llm_model,
                endpoint_url,
                prompt_length,
            )
            # Log full prompt for debugging (truncated to 2000 chars)
            prompt_preview = enhanced_prompt[:2000].replace("\n", "\\n") if isinstance(enhanced_prompt, str) else str(enhanced_prompt)[:2000]
            logger.info("LLM full prompt (first 2000 chars): %s...", prompt_preview)
            
            # Call LLM with error handling
            try:
                # For OpenRouter, use direct HTTP call as LangChain wrapper has compatibility issues
                if self.llm_provider == "openrouter":
                    import requests
                    headers = {
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3000",  # Optional for OpenRouter
                    }
                    payload = {
                        "model": self.llm_model,
                        "messages": [
                            {"role": "user", "content": enhanced_prompt}
                        ],
                        "temperature": 0.9,
                        "max_tokens": 4000,
                    }
                    response_obj = requests.post(
                        f"{endpoint_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=120
                    )
                    response_obj.raise_for_status()
                    response_data = response_obj.json()
                    # Extract the content from the response
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        response = response_data["choices"][0]["message"]["content"]
                    else:
                        raise ValueError(f"Unexpected OpenRouter response format: {response_data}")
                else:
                    # For other providers, use LangChain wrapper
                    if self.llm_provider == "openai" or self.llm_provider == "xai":
                        # OpenAI-compatible API
                        llm = OpenAI(**llm_kwargs)
                    elif self.llm_provider == "local":
                        # Local Ollama - use OpenAI-compatible wrapper
                        llm_kwargs["api_key"] = "ollama"  # Not used but required
                        llm = OpenAI(**llm_kwargs)
                    elif self.llm_provider == "anthropic":
                        # Anthropic Claude - use OpenAI wrapper with custom endpoint
                        llm = OpenAI(**llm_kwargs)
                    else:
                        # Generic OpenAI-compatible
                        llm = OpenAI(**llm_kwargs)
                    
                    response = llm(enhanced_prompt)
                try:
                    logger.info(
                        "LLM raw response (truncated): %s",
                        str(response)[:1000].replace("\n", " "),
                    )
                except Exception:
                    pass
                llm_tests = self._parse_llm_response(response, endpoint)
                tests.extend(llm_tests)
            except Exception as llm_error:
                error_str = str(llm_error)
                logger.error(f"LLM API call failed: {error_str}", exc_info=True)
                
                # Check if it's an API format error (like OpenRouter expecting different format)
                if "Input required: specify" in error_str or "prompt" in error_str.lower():
                    raise RuntimeError(
                        f"LLM API format error: {error_str}. "
                        f"This may indicate that {self.llm_provider} requires a different API format. "
                        f"Try using a different LLM provider (e.g., 'openai' instead of '{self.llm_provider}') or check your LLM endpoint configuration."
                    )
                else:
                    raise RuntimeError(f"LLM API call failed: {error_str}") from llm_error
        
        except RuntimeError:
            # Re-raise RuntimeErrors as-is
            raise
        except Exception as e:
            logger.error(f"LLM test generation error: {str(e)}", exc_info=True)
            raise RuntimeError(f"LLM test generation failed: {str(e)}") from e
        
        # Validate that we have tests
        if not tests or len(tests) == 0:
            raise ValueError("LLM returned no test cases. Check LLM response and configuration.")
        
        return tests