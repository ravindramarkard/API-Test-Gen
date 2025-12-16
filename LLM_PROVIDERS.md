# LLM Provider Configuration Guide

## Supported LLM Providers

The platform now supports multiple LLM providers including local and OpenRouter:

### 1. **OpenAI** (Default)
- **Provider**: `openai`
- **Models**: `gpt-4`, `gpt-3.5-turbo`, `gpt-4-turbo`, etc.
- **Endpoint**: `https://api.openai.com/v1` (default)
- **API Key**: Required (get from https://platform.openai.com/api-keys)

### 2. **xAI (Grok)**
- **Provider**: `xai`
- **Models**: `grok-beta`, etc.
- **Endpoint**: `https://api.x.ai/v1` (default)
- **API Key**: Required (get from https://x.ai/api)

### 3. **Anthropic (Claude)**
- **Provider**: `anthropic`
- **Models**: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`, etc.
- **Endpoint**: `https://api.anthropic.com/v1` (default)
- **API Key**: Required (get from https://console.anthropic.com/)

### 4. **OpenRouter** ⭐ NEW
- **Provider**: `openrouter`
- **Models**: Any model from OpenRouter's catalog
  - Format: `provider/model-name`
  - Examples:
    - `openai/gpt-4`
    - `anthropic/claude-3-opus`
    - `google/gemini-pro`
    - `meta-llama/llama-2-70b-chat`
- **Endpoint**: `https://openrouter.ai/api/v1` (default)
- **API Key**: Required (get from https://openrouter.ai/keys)
- **Benefits**: 
  - Access to multiple LLM providers through one API
  - Pay-per-use pricing
  - No need for multiple API keys

### 5. **Local (Ollama)** ⭐ NEW
- **Provider**: `local`
- **Models**: Any Ollama model (e.g., `llama2`, `mistral`, `codellama`, `phi`)
- **Endpoint**: `http://localhost:11434/v1` (default)
- **API Key**: Not required
- **Setup**:
  1. Install Ollama: https://ollama.ai
  2. Pull a model: `ollama pull llama2`
  3. Start Ollama service
  4. Configure in the UI with provider `local` and model name

## Configuration

### Via Web UI

1. Navigate to: `http://localhost:3000/projects/{project_id}/config`
2. Scroll to **"LLM Configuration"** section
3. Select provider from dropdown
4. Enter model name (see format requirements above)
5. Enter API key (if required)
6. Enter endpoint (or leave empty for default)
7. Click **"Test LLM Connection"** to verify
8. Click **"Save Configuration"**

### Test Connection Feature ⭐ NEW

The **"Test LLM Connection"** button allows you to verify your LLM configuration before saving:

- Tests the connection without saving configuration
- Validates API key (if required)
- Checks endpoint accessibility
- Verifies model availability
- Shows success/error messages

**How to use:**
1. Fill in LLM provider settings
2. Click **"Test LLM Connection"**
3. Wait for result (success ✅ or error ❌)
4. If successful, save configuration
5. If failed, check error message and fix issues

### Via API

**Test Connection Endpoint:**
```bash
POST /api/v1/config/{project_id}/test-llm

{
  "llm_provider": "openrouter",
  "llm_api_key": "sk-or-...",
  "llm_endpoint": "https://openrouter.ai/api/v1",
  "llm_model": "openai/gpt-4"
}
```

**Save Configuration:**
```bash
POST /api/v1/config/{project_id}

{
  "base_url": "https://api.example.com",
  "llm_provider": "local",
  "llm_model": "llama2",
  "llm_endpoint": "http://localhost:11434/v1"
}
```

## Examples

### Local Ollama Setup

1. **Install Ollama**:
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Or download from https://ollama.ai
   ```

2. **Pull a model**:
   ```bash
   ollama pull llama2
   # or
   ollama pull mistral
   ```

3. **Verify Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

4. **Configure in UI**:
   - Provider: `local`
   - Model: `llama2` (or your model name)
   - Endpoint: `http://localhost:11434/v1`
   - API Key: Leave empty

### OpenRouter Setup

1. **Get API Key**: https://openrouter.ai/keys
2. **Configure in UI**:
   - Provider: `openrouter`
   - Model: `openai/gpt-4` (or any model from catalog)
   - Endpoint: `https://openrouter.ai/api/v1` (default)
   - API Key: Your OpenRouter API key

3. **Browse Models**: https://openrouter.ai/models

## Model Name Formats

- **OpenAI**: `gpt-4`, `gpt-3.5-turbo`
- **Anthropic**: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`
- **xAI**: `grok-beta`
- **OpenRouter**: `provider/model-name` (e.g., `openai/gpt-4`, `anthropic/claude-3-opus`)
- **Local (Ollama)**: Model name as shown in `ollama list` (e.g., `llama2`, `mistral`)

## Troubleshooting

### Local Ollama Issues

**Connection Failed:**
- Ensure Ollama is running: `ollama serve` or check service status
- Verify endpoint: `http://localhost:11434/v1`
- Check if model is pulled: `ollama list`
- Test manually: `curl http://localhost:11434/api/generate -d '{"model":"llama2","prompt":"test"}'`

**Model Not Found:**
- Pull the model: `ollama pull {model-name}`
- Use exact model name from `ollama list`

### OpenRouter Issues

**Authentication Failed:**
- Verify API key is correct
- Check API key has credits/quota
- Ensure key format: `sk-or-...`

**Model Not Found:**
- Use correct format: `provider/model-name`
- Check model availability: https://openrouter.ai/models
- Some models may require specific API keys

### General Issues

**Test Connection Fails:**
- Check endpoint URL is correct
- Verify API key (if required)
- Ensure network connectivity
- Check provider service status
- Review error message for details

**LLM Not Generating Tests:**
- Verify configuration is saved
- Check LLM connection test passes
- Review backend logs: `docker-compose logs backend | grep -i llm`
- Ensure sufficient API credits/quota

## Best Practices

1. **Always test connection** before saving configuration
2. **Use local Ollama** for development/testing (free, no API costs)
3. **Use OpenRouter** for production (access to multiple providers, pay-per-use)
4. **Keep API keys secure** - they're encrypted in the database
5. **Monitor usage** - especially for paid providers
6. **Start with simple models** - test with smaller models first

## Cost Considerations

- **Local (Ollama)**: Free (runs on your machine)
- **OpenRouter**: Pay-per-use, competitive pricing
- **OpenAI**: Pay-per-token, varies by model
- **Anthropic**: Pay-per-token, varies by model
- **xAI**: Check current pricing

## Next Steps

1. Choose a provider based on your needs
2. Get API key (if required)
3. Configure in the UI
4. Test connection
5. Save configuration
6. Generate tests and see AI-enhanced test cases!




