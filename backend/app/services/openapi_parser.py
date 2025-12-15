"""
OpenAPI/Swagger specification parser with $ref resolution.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

import prance
from openapi_spec_validator import validate_spec

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """Parser for OpenAPI specifications with $ref resolution."""
    
    def __init__(self, spec_path: Optional[str] = None, spec_dict: Optional[Dict] = None):
        """
        Initialize parser.
        
        Args:
            spec_path: Path to OpenAPI file
            spec_dict: OpenAPI spec as dictionary
        """
        self.spec_path = spec_path
        self.spec_dict = spec_dict
        self.resolved_spec: Optional[Dict] = None
        self.collections: Dict[str, Any] = {}
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse and resolve OpenAPI specification.
        
        Returns:
            Resolved OpenAPI specification
        """
        try:
            # Load spec
            if self.spec_path:
                parser = prance.ResolvingParser(self.spec_path)
            elif self.spec_dict:
                # Write to temp file for prance
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(self.spec_dict, f)
                    temp_path = f.name
                
                parser = prance.ResolvingParser(temp_path)
                Path(temp_path).unlink()  # Clean up
            else:
                raise ValueError("Either spec_path or spec_dict must be provided")
            
            # Get resolved spec
            self.resolved_spec = parser.specification
            
            # Validate
            validate_spec(self.resolved_spec)
            
            # Extract collections (reusable schemas)
            self._extract_collections()
            
            logger.info(f"Successfully parsed OpenAPI spec with {len(self.collections)} collections")
            
            return self.resolved_spec
        
        except Exception as e:
            logger.error(f"Error parsing OpenAPI spec: {str(e)}")
            raise
    
    def _extract_collections(self):
        """Extract reusable schema collections from components/schemas."""
        if not self.resolved_spec:
            return
        
        # OpenAPI 3.x
        if 'components' in self.resolved_spec and 'schemas' in self.resolved_spec['components']:
            self.collections = self.resolved_spec['components']['schemas']
        
        # Swagger 2.0
        elif 'definitions' in self.resolved_spec:
            self.collections = self.resolved_spec['definitions']
    
    def get_endpoints(self) -> List[Dict[str, Any]]:
        """
        Extract all API endpoints from the spec.
        
        Returns:
            List of endpoint definitions
        """
        if not self.resolved_spec:
            raise ValueError("Spec not parsed. Call parse() first.")
        
        endpoints = []
        paths = self.resolved_spec.get('paths', {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                    endpoints.append({
                        'path': path,
                        'method': method.upper(),
                        'operation': operation,
                        'operation_id': operation.get('operationId', f"{method.upper()}_{path}"),
                        'summary': operation.get('summary', ''),
                        'parameters': operation.get('parameters', []),
                        'request_body': operation.get('requestBody', {}),
                        'responses': operation.get('responses', {}),
                    })
        
        return endpoints
    
    def get_schemas(self) -> Dict[str, Any]:
        """Get all schemas/collections."""
        return self.collections
    
    def resolve_ref(self, ref: str) -> Dict[str, Any]:
        """
        Resolve a $ref reference.
        
        Args:
            ref: Reference string (e.g., '#/components/schemas/User')
        
        Returns:
            Resolved schema
        """
        if not ref.startswith('#'):
            # External ref - would need to fetch
            raise ValueError(f"External references not supported: {ref}")
        
        parts = ref.split('/')[1:]  # Remove '#'
        current = self.resolved_spec
        
        for part in parts:
            if part in current:
                current = current[part]
            else:
                raise ValueError(f"Reference not found: {ref}")
        
        return current


