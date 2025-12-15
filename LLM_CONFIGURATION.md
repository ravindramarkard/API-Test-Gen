# LLM Configuration Guide

## Where to Configure LLM Connection

### 1. **Via Web UI (Recommended)**

1. Navigate to your project: `http://localhost:3000/projects/{project_id}`
2. Click the **"Configure"** button (top right)
3. Scroll down to the **"LLM Configuration"** section
4. Fill in:
   - **LLM Provider**: Select from OpenAI, xAI (Grok), or Anthropic (Claude)
   - **LLM Model**: Enter model name (e.g., `gpt-4`, `gpt-3.5-turbo`)
   - **LLM API Key**: Enter your API key (encrypted and stored securely)
   - **Custom LLM Endpoint** (Optional): For custom endpoints
5. Click **"Save Configuration"**

**URL**: `http://localhost:3000/projects/{project_id}/config`

### 2. **Via API**

**Endpoint**: `POST /api/v1/config/{project_id}`

**Request Body**:
```json
{
  "base_url": "https://api.example.com",
  "llm_provider": "openai",
  "llm_api_key": "sk-your-api-key-here",
  "llm_model": "gpt-4",
  "llm_endpoint": "https://api.openai.com/v1"  // Optional
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/config/69f060d0-7a82-4e7c-b3ca-c2631ce1e377 \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://api.example.com",
    "llm_provider": "openai",
    "llm_api_key": "sk-your-key",
    "llm_model": "gpt-4"
  }'
```

### 3. **Supported LLM Providers**

- **OpenAI**: `llm_provider: "openai"`
  - Models: `gpt-4`, `gpt-3.5-turbo`, etc.
  - Endpoint: `https://api.openai.com/v1` (default)

- **xAI (Grok)**: `llm_provider: "xai"`
  - Models: `grok-beta`, etc.
  - Endpoint: `https://api.x.ai/v1` (default)
  - Get API key: https://x.ai/api

- **Anthropic (Claude)**: `llm_provider: "anthropic"`
  - Models: `claude-3-opus`, `claude-3-sonnet`, etc.
  - Endpoint: `https://api.anthropic.com/v1` (default)

### 4. **Where LLM is Used**

The LLM connection is used when:
- **Generating Tests**: Click "Generate Tests" on a project
- The system uses LLM to create:
  - Security test cases (XSS, SQL injection)
  - Edge case scenarios
  - Advanced validation tests
  - Performance test suggestions

**Location in Code**:
- Frontend Config: `frontend/src/pages/Config.tsx`
- Backend Config Endpoint: `backend/app/api/v1/endpoints/config.py`
- Test Generator: `backend/app/services/test_generator.py`
- Database Model: `backend/app/db/models.py` (ProjectConfig)

### 5. **Security**

- LLM API keys are **encrypted** using Fernet encryption
- Keys are stored in the `project_configs` table
- Keys are never exposed in API responses
- Only the presence of a key is indicated (`has_llm_key: true/false`)

### 6. **Testing LLM Connection**

After configuring:
1. Go to your project page
2. Click "Generate Tests"
3. The system will:
   - Use baseline tests (no LLM required)
   - Use LLM-enhanced tests (if LLM is configured)
4. Check the generated test suite for AI-generated test cases

### 7. **Troubleshooting**

**LLM not working?**
- Verify API key is correct
- Check API key has sufficient credits/quota
- Verify endpoint URL is correct (for custom endpoints)
- Check backend logs: `docker-compose logs backend | grep -i llm`

**No LLM tests generated?**
- LLM is optional - baseline tests will still be generated
- Check if LLM API key is configured
- Verify LLM provider endpoint is accessible
- Check error logs in the test generation response

## Quick Start

1. **Get an API Key**:
   - OpenAI: https://platform.openai.com/api-keys
   - xAI: https://x.ai/api
   - Anthropic: https://console.anthropic.com/

2. **Configure in UI**:
   - Go to: `http://localhost:3000/projects/{your-project-id}/config`
   - Scroll to "LLM Configuration"
   - Enter your API key and model
   - Save

3. **Generate Tests**:
   - Go back to project page
   - Click "Generate Tests"
   - Review AI-enhanced test cases


