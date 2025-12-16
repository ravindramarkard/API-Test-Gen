"""
Tests for OpenAPI parser.
"""
import pytest
from app.services.openapi_parser import OpenAPIParser


def test_parse_simple_openapi():
    """Test parsing a simple OpenAPI spec."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0"
        },
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            }
        }
    }
    
    parser = OpenAPIParser(spec_dict=spec)
    resolved = parser.parse()
    
    assert resolved is not None
    assert resolved["info"]["title"] == "Test API"
    
    endpoints = parser.get_endpoints()
    assert len(endpoints) == 1
    assert endpoints[0]["path"] == "/users"
    assert endpoints[0]["method"] == "GET"




