"""
Project configuration endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.db.database import get_db
from app.db.models import Project, ProjectConfig
from app.core.security import encrypt_data, decrypt_data
from app.services.activity_logger import log_activity

router = APIRouter()


class ConfigCreate(BaseModel):
    """Configuration creation model."""
    base_url: str = Field(..., description="Base URL for API")
    auth_type: Optional[str] = Field(None, description="Authentication type: basic, bearer, api_key, oauth2")
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None
    auth_key_name: Optional[str] = None
    auth_key_value: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_authorization_url: Optional[str] = None
    oauth2_scope: Optional[str] = None
    oauth2_grant_type: Optional[str] = Field("client_credentials", description="OAuth2 grant type")
    llm_provider: Optional[str] = Field("openai", description="LLM provider")
    llm_api_key: Optional[str] = None
    llm_endpoint: Optional[str] = None
    llm_model: Optional[str] = Field("gpt-4", description="LLM model name")


class LLMTestRequest(BaseModel):
    """LLM connection test request."""
    llm_provider: str
    llm_api_key: Optional[str] = None
    llm_endpoint: Optional[str] = None
    llm_model: Optional[str] = "gpt-4"


class APITestRequest(BaseModel):
    """API connection test request."""
    base_url: str
    auth_type: Optional[str] = None
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None
    auth_key_name: Optional[str] = None
    auth_key_value: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_authorization_url: Optional[str] = None
    oauth2_scope: Optional[str] = None
    oauth2_grant_type: Optional[str] = "client_credentials"


@router.post("/{project_id}")
def create_config(
    project_id: UUID,
    config: ConfigCreate,
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """Create or update project configuration."""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if config exists
    existing_config = db.query(ProjectConfig).filter(
        ProjectConfig.project_id == project_id
    ).first()
    
    # Prepare auth credentials
    import json
    auth_credentials = None
    if config.auth_type:
        if config.auth_type == 'basic':
            auth_credentials = encrypt_data(json.dumps({
                'username': config.auth_username,
                'password': config.auth_password
            }))
        elif config.auth_type == 'bearer':
            auth_credentials = encrypt_data(json.dumps({
                'token': config.auth_token
            }))
        elif config.auth_type == 'api_key':
            auth_credentials = encrypt_data(json.dumps({
                'key_name': config.auth_key_name or 'X-API-Key',
                'key_value': config.auth_key_value
            }))
        elif config.auth_type == 'oauth2':
            if not config.oauth2_token_url or not config.oauth2_client_id or not config.oauth2_client_secret:
                raise HTTPException(
                    status_code=400,
                    detail="OAuth2 requires token_url, client_id, and client_secret"
                )
            auth_credentials = encrypt_data(json.dumps({
                'client_id': config.oauth2_client_id,
                'client_secret': config.oauth2_client_secret,
                'token_url': config.oauth2_token_url,
                'authorization_url': config.oauth2_authorization_url,
                'scope': config.oauth2_scope,
                'grant_type': config.oauth2_grant_type or 'client_credentials'
            }))
    
    # Store LLM API key directly (no encryption) - user can update via config endpoint
    # Set default endpoints for providers
    if not config.llm_endpoint:
        if config.llm_provider == 'local':
            config.llm_endpoint = 'http://localhost:11434/v1'
        elif config.llm_provider == 'openrouter':
            config.llm_endpoint = 'https://openrouter.ai/api/v1'
    
    if existing_config:
        # Update existing
        existing_config.base_url = config.base_url
        existing_config.auth_type = config.auth_type
        if auth_credentials:
            existing_config.auth_credentials = auth_credentials
        existing_config.llm_provider = config.llm_provider
        # Store LLM API key directly (no encryption) if provided
        if config.llm_api_key and config.llm_provider != 'local':
            existing_config.llm_api_key = config.llm_api_key
        existing_config.llm_endpoint = config.llm_endpoint
        existing_config.llm_model = config.llm_model
        db.commit()
        db.refresh(existing_config)

        # Log activity
        try:
            log_activity(
                db=db,
                project_id=project_id,
                action="updated_config",
                actor=x_actor,
                details={
                    "config_id": str(existing_config.id),
                    "base_url": existing_config.base_url,
                    "auth_type": existing_config.auth_type,
                    "llm_provider": existing_config.llm_provider,
                    "llm_model": existing_config.llm_model,
                },
            )
        except Exception:
            pass

        return {"message": "Configuration updated", "config_id": str(existing_config.id)}
    else:
        # Create new
        new_config = ProjectConfig(
            project_id=project_id,
            base_url=config.base_url,
            auth_type=config.auth_type,
            auth_credentials=auth_credentials,
            llm_provider=config.llm_provider,
            llm_api_key=config.llm_api_key if config.llm_api_key and config.llm_provider != 'local' else None,  # Store directly (no encryption)
            llm_endpoint=config.llm_endpoint,
            llm_model=config.llm_model or "gpt-4"
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)

        # Log activity
        try:
            log_activity(
                db=db,
                project_id=project_id,
                action="created_config",
                actor=x_actor,
                details={
                    "config_id": str(new_config.id),
                    "base_url": new_config.base_url,
                    "auth_type": new_config.auth_type,
                    "llm_provider": new_config.llm_provider,
                    "llm_model": new_config.llm_model,
                },
            )
        except Exception:
            pass

        return {"message": "Configuration created", "config_id": str(new_config.id)}


@router.delete("/{project_id}/llm-key")
def clear_llm_api_key(
    project_id: UUID,
    db: Session = Depends(get_db),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
):
    """Clear the stored LLM API key."""
    config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Project configuration not found")
    
    config.llm_api_key = None
    db.commit()
    
    # Log activity
    try:
        log_activity(
            db=db,
            project_id=project_id,
            action="cleared_llm_key",
            actor=x_actor,
            details={
                "config_id": str(config.id),
                "reason": "User cleared LLM API key"
            },
        )
    except Exception:
        pass
    
    return {"message": "LLM API key cleared. Please update it in Project Configuration when needed."}


@router.get("/")
def list_configs(db: Session = Depends(get_db)):
    """List available project configs (non-sensitive) for reuse."""
    configs = (
        db.query(ProjectConfig, Project)
        .join(Project, ProjectConfig.project_id == Project.id)
        .all()
    )
    results = []
    for cfg, project in configs:
        results.append({
            "project_id": str(cfg.project_id),
            "project_name": project.name,
            "config_id": str(cfg.id),
            "base_url": cfg.base_url,
            "auth_type": cfg.auth_type,
            "llm_provider": cfg.llm_provider,
            "llm_model": cfg.llm_model,
            "llm_endpoint": cfg.llm_endpoint,
            "has_auth": bool(cfg.auth_credentials),
            "has_llm_key": bool(cfg.llm_api_key),
        })
    return {"configs": results}


@router.post("/{project_id}/test-llm")
def test_llm_connection(
    project_id: UUID,
    test_request: LLMTestRequest,
    db: Session = Depends(get_db)
):
    """Test LLM connection without saving configuration."""
    import requests
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    
    try:
        # Load stored config to reuse secrets if not provided
        stored_config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
        
        logger.info(f"Test LLM connection request: provider={test_request.llm_provider}, has_key_in_request={bool(test_request.llm_api_key)}, has_stored_config={bool(stored_config)}")
        
        if stored_config:
            # Reuse provider/model/endpoint if not supplied
            if not test_request.llm_provider:
                test_request.llm_provider = stored_config.llm_provider or test_request.llm_provider
            if not test_request.llm_model:
                test_request.llm_model = stored_config.llm_model or test_request.llm_model
            if not test_request.llm_endpoint:
                test_request.llm_endpoint = stored_config.llm_endpoint
            # Reuse API key if not supplied (stored directly, no decryption needed)
            if not test_request.llm_api_key and stored_config.llm_api_key:
                test_request.llm_api_key = stored_config.llm_api_key
                logger.info("Using stored LLM API key for test connection")
            else:
                logger.info(f"Not using stored key: has_key_in_request={bool(test_request.llm_api_key)}, has_stored_key={bool(stored_config.llm_api_key)}")
        
        # Fallback to environment variable if not in database and not provided
        if not test_request.llm_api_key and test_request.llm_provider != 'local':
            from app.core.config import settings
            if settings.LLM_API_KEY and settings.LLM_API_KEY.strip():
                test_request.llm_api_key = settings.LLM_API_KEY
                logger.info("Using LLM API key from environment variable for test connection")
            else:
                logger.warning("No LLM API key found in environment variable")
        
        # Validate that we have an API key for non-local providers
        if not test_request.llm_api_key and test_request.llm_provider != 'local':
            logger.error(f"LLM API key validation failed: provider={test_request.llm_provider}, has_key={bool(test_request.llm_api_key)}")
            raise HTTPException(
                status_code=400,
                detail="LLM API key is required for this provider. Please configure it in Project Configuration or set LLM_API_KEY environment variable."
            )
        
        logger.info(f"Final LLM test config: provider={test_request.llm_provider}, has_key={bool(test_request.llm_api_key)}, endpoint={test_request.llm_endpoint}")

        # Determine endpoint
        endpoint = test_request.llm_endpoint
        if endpoint:
            endpoint = endpoint.strip()  # Remove leading/trailing whitespace
        
        if not endpoint:
            if test_request.llm_provider == 'local':
                endpoint = 'http://localhost:11434'
            elif test_request.llm_provider == 'openrouter':
                endpoint = 'https://openrouter.ai/api/v1'
            elif test_request.llm_provider == 'openai':
                endpoint = 'https://api.openai.com/v1'
            elif test_request.llm_provider == 'xai':
                endpoint = 'https://api.x.ai/v1'
            elif test_request.llm_provider == 'anthropic':
                endpoint = 'https://api.anthropic.com/v1'
            else:
                endpoint = 'https://api.openai.com/v1'
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Add API key if provided (not needed for local Ollama)
        if test_request.llm_api_key and test_request.llm_provider != 'local':
            if test_request.llm_provider == 'openrouter':
                headers['HTTP-Referer'] = 'http://localhost:3000'  # Optional for OpenRouter
                headers['Authorization'] = f'Bearer {test_request.llm_api_key}'
            elif test_request.llm_provider == 'anthropic':
                headers['x-api-key'] = test_request.llm_api_key
                headers['anthropic-version'] = '2023-06-01'
            else:
                headers['Authorization'] = f'Bearer {test_request.llm_api_key}'
        
        # Prepare test payload and URL based on provider
        if test_request.llm_provider == 'anthropic':
            payload = {
                'model': test_request.llm_model or 'claude-3-sonnet-20240229',
                'max_tokens': 10,
                'messages': [{'role': 'user', 'content': 'Hi'}]
            }
            test_url = f"{endpoint}/messages"
        elif test_request.llm_provider == 'local':
            # Ollama supports both old /api/generate and new OpenAI-compatible /v1/chat/completions
            # Check if endpoint contains /api/chat or /v1/chat or /chat/completions (OpenAI-compatible)
            endpoint_lower = endpoint.lower()
            if '/api/chat' in endpoint_lower or '/v1/chat' in endpoint_lower or '/chat/completions' in endpoint_lower:
                # Use OpenAI-compatible format
                # Normalize endpoint: remove /api/chat, /v1/chat, /chat/completions, /v1
                base_endpoint = endpoint.rstrip('/')
                base_endpoint = base_endpoint.replace('/api/chat', '').replace('/v1/chat', '').replace('/chat/completions', '').replace('/v1', '')
                if not base_endpoint.endswith('/v1'):
                    base_endpoint = base_endpoint.rstrip('/') + '/v1'
                test_url = f"{base_endpoint}/chat/completions"
                payload = {
                    'model': test_request.llm_model or 'llama2',
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 10
                }
            else:
                # Use old /api/generate format
                base_endpoint = endpoint.rstrip('/').replace('/v1', '').replace('/api/generate', '')
                test_url = f"{base_endpoint}/api/generate"
                payload = {
                    'model': test_request.llm_model or 'llama2',
                    'prompt': 'Hi',
                    'stream': False
                }
        else:
            # OpenAI-compatible format (OpenAI, OpenRouter, xAI)
            payload = {
                'model': test_request.llm_model or 'gpt-4',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'max_tokens': 10
            }
            # Ensure endpoint ends with /v1 if not already
            if not endpoint.endswith('/v1') and not endpoint.endswith('/v1/'):
                endpoint = endpoint.rstrip('/') + '/v1'
            test_url = f"{endpoint}/chat/completions"
        
        # Make test request
        logger.info(f"Testing LLM connection: {test_request.llm_provider} at {test_url}")
        response = requests.post(
            test_url,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "message": f"Successfully connected to {test_request.llm_provider}",
                "provider": test_request.llm_provider,
                "endpoint": endpoint
            }
        else:
            error_detail = response.text[:500] if response.text else "Unknown error"
            logger.error(f"LLM test failed: {response.status_code} - {error_detail}")
            raise HTTPException(
                status_code=400,
                detail=f"Connection failed: {response.status_code} - {error_detail}"
            )
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error to LLM endpoint: {str(e)}")
        error_msg = f"Could not connect to LLM endpoint: {test_url}"
        if test_request.llm_provider == 'local' and 'localhost' in endpoint:
            error_msg += "\n\nNote: If Ollama is running on your host machine (not in Docker), try using 'host.docker.internal' instead of 'localhost'.\nExample: http://host.docker.internal:11434/api/chat"
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=400,
            detail="Connection timeout. The LLM service may be slow or unavailable."
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like decryption errors) as-is
        raise
    except Exception as e:
        logger.error(f"LLM test error: {str(e)}", exc_info=True)
        # Check if it's a decryption error that wasn't caught
        error_str = str(e).lower()
        if "decrypt" in error_str or "decryption" in error_str or "failed to decrypt" in error_str:
            raise HTTPException(
                status_code=400,
                detail="Stored LLM API key could not be decrypted. Please re-enter your LLM API key and try again."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )


@router.post("/{project_id}/test-api")
def test_api_connection(
    project_id: UUID,
    test_request: APITestRequest,
    db: Session = Depends(get_db)
):
    """Test API connection without saving configuration."""
    import requests
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Load stored config to reuse secrets if not provided
        stored_config = db.query(ProjectConfig).filter(ProjectConfig.project_id == project_id).first()
        stored_auth = None
        if stored_config:
            # Fill missing base_url/auth_type from stored
            if not test_request.base_url:
                test_request.base_url = stored_config.base_url
            if not test_request.auth_type:
                test_request.auth_type = stored_config.auth_type
            if stored_config.auth_credentials:
                try:
                    stored_auth = json.loads(decrypt_data(stored_config.auth_credentials))
                except Exception:
                    stored_auth = None

        # Validate base URL
        base_url = test_request.base_url.strip().rstrip('/')
        if not base_url:
            raise HTTPException(status_code=400, detail="Base URL is required")
        
        if not base_url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Base URL must start with http:// or https://")
        
        # Prepare session with authentication
        session = requests.Session()
        
        # Setup authentication
        if test_request.auth_type == 'basic':
            if test_request.auth_username and test_request.auth_password:
                session.auth = (test_request.auth_username, test_request.auth_password)
            elif stored_auth:
                if stored_auth.get('username') and stored_auth.get('password'):
                    session.auth = (stored_auth.get('username'), stored_auth.get('password'))
        elif test_request.auth_type == 'bearer':
            if test_request.auth_token:
                session.headers.update({'Authorization': f'Bearer {test_request.auth_token}'})
            elif stored_auth and stored_auth.get('token'):
                session.headers.update({'Authorization': f'Bearer {stored_auth.get("token")}'})
        elif test_request.auth_type == 'api_key':
            if test_request.auth_key_name and test_request.auth_key_value:
                session.headers.update({test_request.auth_key_name: test_request.auth_key_value})
            elif stored_auth and stored_auth.get('key_name') and stored_auth.get('key_value'):
                session.headers.update({stored_auth.get('key_name'): stored_auth.get('key_value')})
        elif test_request.auth_type == 'oauth2':
            # Test OAuth2 token acquisition
            # Pull missing pieces from stored auth if available
            if stored_auth:
                test_request.oauth2_token_url = test_request.oauth2_token_url or stored_auth.get('token_url')
                test_request.oauth2_client_id = test_request.oauth2_client_id or stored_auth.get('client_id')
                test_request.oauth2_client_secret = test_request.oauth2_client_secret or stored_auth.get('client_secret')
                test_request.oauth2_authorization_url = test_request.oauth2_authorization_url or stored_auth.get('authorization_url')
                test_request.oauth2_scope = test_request.oauth2_scope or stored_auth.get('scope')
                test_request.oauth2_grant_type = test_request.oauth2_grant_type or stored_auth.get('grant_type')

            if not test_request.oauth2_token_url or not test_request.oauth2_client_id or not test_request.oauth2_client_secret:
                raise HTTPException(
                    status_code=400,
                    detail="OAuth2 requires token_url, client_id, and client_secret"
                )
            
            # Try to get OAuth2 token
            token_data = {
                'grant_type': test_request.oauth2_grant_type or 'client_credentials',
                'client_id': test_request.oauth2_client_id,
                'client_secret': test_request.oauth2_client_secret,
            }
            
            if test_request.oauth2_scope:
                token_data['scope'] = test_request.oauth2_scope
            
            token_response = requests.post(
                test_request.oauth2_token_url,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if token_response.status_code != 200:
                error_detail = token_response.text[:500] if token_response.text else "Unknown error"
                raise HTTPException(
                    status_code=400,
                    detail=f"OAuth2 token acquisition failed: {token_response.status_code} - {error_detail}"
                )
            
            # Check if response is JSON
            content_type = token_response.headers.get('Content-Type', '').lower()
            if 'application/json' not in content_type:
                # Try to parse as JSON anyway, but handle errors gracefully
                try:
                    token_json = token_response.json()
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_detail = token_response.text[:500] if token_response.text else "Unknown error"
                    raise HTTPException(
                        status_code=400,
                        detail=f"OAuth2 token endpoint returned non-JSON response. Make sure you're using the token endpoint (e.g., /oauth/token), not the authorization endpoint (e.g., /oauth/authorize). Response: {error_detail[:200]}"
                    )
            else:
                token_json = token_response.json()
            
            access_token = token_json.get('access_token')
            if not access_token:
                # Check if there's an error in the response
                error = token_json.get('error', 'Unknown error')
                error_description = token_json.get('error_description', '')
                error_msg = f"OAuth2 token response missing access_token. Error: {error}"
                if error_description:
                    error_msg += f" - {error_description}"
                raise HTTPException(
                    status_code=400,
                    detail=error_msg
                )
            
            session.headers.update({'Authorization': f'Bearer {access_token}'})
        
        # Test connection with a simple GET request to the base URL
        # Try common health/status endpoints first
        test_endpoints = ['/', '/health', '/status', '/api/health', '/api/status']
        test_url = None
        response = None
        
        for endpoint in test_endpoints:
            try:
                test_url = f"{base_url}{endpoint}"
                logger.info(f"Testing API connection at: {test_url}")
                response = session.get(test_url, timeout=10, allow_redirects=True)
                # Accept any 2xx, 3xx, or 4xx status (4xx means server is reachable)
                if response.status_code < 500:
                    break
            except requests.exceptions.RequestException:
                continue
        
        # If all common endpoints failed, try the base URL directly
        if not response or response.status_code >= 500:
            test_url = base_url
            logger.info(f"Testing API connection at base URL: {test_url}")
            response = session.get(test_url, timeout=10, allow_redirects=True)
        
        # Determine success
        # Success if we get any response (even 404 means server is reachable)
        if response.status_code < 500:
            return {
                "success": True,
                "message": f"Successfully connected to API",
                "base_url": base_url,
                "test_url": test_url,
                "status_code": response.status_code,
                "auth_type": test_request.auth_type or "None",
                "auth_status": "configured" if test_request.auth_type else "not configured"
            }
        else:
            error_detail = response.text[:500] if response.text else "Unknown error"
            raise HTTPException(
                status_code=400,
                detail=f"API connection failed: {response.status_code} - {error_detail}"
            )
    
    except HTTPException:
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error to API endpoint: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to API endpoint: {base_url}. Check if the service is running and the URL is correct."
        )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=400,
            detail="Connection timeout. The API service may be slow or unavailable."
        )
    except Exception as e:
        logger.error(f"API test error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )


@router.get("/{project_id}")
def get_config(project_id: UUID, db: Session = Depends(get_db)):
    """Get project configuration (without sensitive data)."""
    config = db.query(ProjectConfig).filter(
        ProjectConfig.project_id == project_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return {
        "config_id": str(config.id),
        "base_url": config.base_url,
        "auth_type": config.auth_type,
        "llm_provider": config.llm_provider,
        "llm_model": config.llm_model,
        "llm_endpoint": config.llm_endpoint,
        "has_auth": bool(config.auth_credentials),
        "has_llm_key": bool(config.llm_api_key),
    }
