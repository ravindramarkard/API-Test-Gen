import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import { Save, CheckCircle } from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../hooks/redux';
import { fetchConfig, saveConfig } from '../store/slices/configSlice';
import api from '../services/api';

const Config: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { config, loading } = useAppSelector((state) => state.config);

  const [configOptions, setConfigOptions] = useState<Array<{
    config_id: string;
    project_id: string;
    project_name: string;
    base_url: string;
    auth_type?: string;
    llm_provider?: string;
    llm_model?: string;
    llm_endpoint?: string;
  }>>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<string>('');

  const [formData, setFormData] = useState({
    base_url: '',
    auth_type: '',
    auth_username: '',
    auth_password: '',
    auth_token: '',
    auth_key_name: 'X-API-Key',
    auth_key_value: '',
    oauth2_client_id: '',
    oauth2_client_secret: '',
    oauth2_token_url: '',
    oauth2_authorization_url: '',
    oauth2_scope: '',
    oauth2_grant_type: 'client_credentials',
    llm_provider: 'openai',
    llm_api_key: '',
    llm_endpoint: '',
    llm_model: 'gpt-4',
  });

  useEffect(() => {
    if (projectId) {
      dispatch(fetchConfig(projectId));
    }
    // fetch reusable configs (non-sensitive)
    const fetchConfigs = async () => {
      try {
        const res = await api.get('/config');
        setConfigOptions(res.data.configs || []);
      } catch (err) {
        console.error('Failed to fetch config options', err);
      }
    };
    fetchConfigs();
  }, [dispatch, projectId]);

  useEffect(() => {
    if (config) {
      setFormData((prev) => ({
        ...prev,
        base_url: config.base_url || '',
        auth_type: config.auth_type || '',
        llm_provider: config.llm_provider || 'openai',
        llm_model: config.llm_model || 'gpt-4',
        llm_endpoint: config.llm_endpoint || '',
      }));
    }
  }, [config]);

  const handleLoadConfigTemplate = (configId: string) => {
    setSelectedConfigId(configId);
    const template = configOptions.find((c) => c.config_id === configId);
    if (!template) return;
    setFormData((prev) => ({
      ...prev,
      base_url: template.base_url || '',
      auth_type: template.auth_type || '',
      llm_provider: template.llm_provider || 'openai',
      llm_model: template.llm_model || 'gpt-4',
      llm_endpoint: template.llm_endpoint || '',
      // clear sensitive fields; user must re-enter
      auth_username: '',
      auth_password: '',
      auth_token: '',
      auth_key_name: 'X-API-Key',
      auth_key_value: '',
      oauth2_client_id: '',
      oauth2_client_secret: '',
      oauth2_token_url: '',
      oauth2_authorization_url: '',
      oauth2_scope: '',
      oauth2_grant_type: 'client_credentials',
      llm_api_key: '',
    }));
  };

  const handleChange = (field: string) => (event: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: event.target.value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (projectId) {
      await dispatch(saveConfig({ projectId, config: formData }));
      navigate(`/projects/${projectId}`);
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Project Configuration
      </Typography>

      <Card sx={{ maxWidth: 900, mx: 'auto', mt: 4 }}>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <Box display="flex" gap={2} flexWrap="wrap" alignItems="center" mb={3}>
              <FormControl sx={{ minWidth: 280 }} size="small">
                <InputLabel>Load Existing Config</InputLabel>
                <Select
                  label="Load Existing Config"
                  value={selectedConfigId}
                  onChange={(e) => handleLoadConfigTemplate(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="">
                    <em>Manual entry</em>
                  </MenuItem>
                  {configOptions.map((opt) => (
                    <MenuItem key={opt.config_id} value={opt.config_id}>
                      {opt.project_name} ({opt.base_url || 'no base url'})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Typography variant="body2" color="textSecondary">
                Selecting a config fills non-sensitive fields. Re-enter secrets (tokens, client secrets, API keys).
              </Typography>
            </Box>

            <Typography variant="h6" gutterBottom>
              API Configuration
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Base URL"
                  value={formData.base_url}
                  onChange={handleChange('base_url')}
                  required
                  placeholder="https://api.example.com"
                  helperText="Base URL for your API"
                />
              </Grid>

              <Grid item xs={12}>
                <FormControl fullWidth>
                  <InputLabel>Authentication Type</InputLabel>
                  <Select
                    value={formData.auth_type}
                    onChange={handleChange('auth_type')}
                    label="Authentication Type"
                  >
                    <MenuItem value="">None</MenuItem>
                    <MenuItem value="basic">Basic Auth</MenuItem>
                    <MenuItem value="bearer">Bearer Token</MenuItem>
                    <MenuItem value="api_key">API Key</MenuItem>
                    <MenuItem value="oauth2">OAuth2</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              {formData.auth_type === 'basic' && (
                <>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Username"
                      value={formData.auth_username}
                      onChange={handleChange('auth_username')}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Password"
                      type="password"
                      value={formData.auth_password}
                      onChange={handleChange('auth_password')}
                      helperText={config?.has_auth ? "Credential on file. Leave empty to keep existing, enter to replace." : undefined}
                    />
                  </Grid>
                </>
              )}

              {formData.auth_type === 'bearer' && (
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Bearer Token"
                    type="password"
                    value={formData.auth_token}
                    onChange={handleChange('auth_token')}
                    helperText={config?.has_auth ? "Token on file. Leave empty to keep existing, enter to replace." : undefined}
                  />
                </Grid>
              )}

              {formData.auth_type === 'api_key' && (
                <>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Key Name"
                      value={formData.auth_key_name}
                      onChange={handleChange('auth_key_name')}
                      placeholder="X-API-Key"
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Key Value"
                      type="password"
                      value={formData.auth_key_value}
                      onChange={handleChange('auth_key_value')}
                      helperText={config?.has_auth ? "Key on file. Leave empty to keep existing, enter to replace." : undefined}
                    />
                  </Grid>
                </>
              )}

              {formData.auth_type === 'oauth2' && (
                <>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Token URL"
                      value={formData.oauth2_token_url}
                      onChange={handleChange('oauth2_token_url')}
                      required
                      placeholder="https://api.example.com/oauth/token"
                      helperText="OAuth2 token endpoint URL"
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Client ID"
                      value={formData.oauth2_client_id}
                      onChange={handleChange('oauth2_client_id')}
                      required
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Client Secret"
                      type="password"
                      value={formData.oauth2_client_secret}
                      onChange={handleChange('oauth2_client_secret')}
                      required
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Authorization URL (Optional)"
                      value={formData.oauth2_authorization_url}
                      onChange={handleChange('oauth2_authorization_url')}
                      placeholder="https://api.example.com/oauth/authorize"
                      helperText="Required for authorization code flow"
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Scope (Optional)"
                      value={formData.oauth2_scope}
                      onChange={handleChange('oauth2_scope')}
                      placeholder="read write"
                      helperText="Space-separated list of scopes"
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <FormControl fullWidth>
                      <InputLabel>Grant Type</InputLabel>
                      <Select
                        value={formData.oauth2_grant_type}
                        onChange={handleChange('oauth2_grant_type')}
                        label="Grant Type"
                      >
                        <MenuItem value="client_credentials">Client Credentials</MenuItem>
                        <MenuItem value="authorization_code">Authorization Code</MenuItem>
                        <MenuItem value="password">Password (Resource Owner Password)</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                </>
              )}
            </Grid>

            <Divider sx={{ my: 4 }} />

            <Typography variant="h6" gutterBottom>
              LLM Configuration (for AI-enhanced test generation)
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>LLM Provider</InputLabel>
                  <Select
                    value={formData.llm_provider}
                    onChange={handleChange('llm_provider')}
                    label="LLM Provider"
                  >
                    <MenuItem value="openai">OpenAI</MenuItem>
                    <MenuItem value="xai">xAI (Grok)</MenuItem>
                    <MenuItem value="anthropic">Anthropic (Claude)</MenuItem>
                    <MenuItem value="openrouter">OpenRouter</MenuItem>
                    <MenuItem value="local">Local (Ollama)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="LLM Model"
                  value={formData.llm_model}
                  onChange={handleChange('llm_model')}
                  placeholder={
                    formData.llm_provider === 'local'
                      ? "llama2, mistral, etc."
                      : formData.llm_provider === 'openrouter'
                      ? "openai/gpt-4, anthropic/claude-3-opus, etc."
                      : "gpt-4"
                  }
                  helperText={
                    formData.llm_provider === 'local'
                      ? "Ollama model name (e.g., llama2, mistral)"
                      : formData.llm_provider === 'openrouter'
                      ? "Model in format: provider/model-name"
                      : undefined
                  }
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="LLM API Key"
                  type="password"
                  value={formData.llm_api_key}
                  onChange={handleChange('llm_api_key')}
                  helperText={
                    formData.llm_provider === 'local'
                      ? "Not required for local Ollama (leave empty)"
                      : config?.has_llm_key
                        ? "Key on file. Leave empty to keep existing, enter to replace."
                        : formData.llm_provider === 'openrouter'
                          ? "Your OpenRouter API key (get from https://openrouter.ai)"
                          : "Your API key for the selected LLM provider"
                  }
                  disabled={formData.llm_provider === 'local'}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="LLM Endpoint"
                  value={formData.llm_endpoint}
                  onChange={handleChange('llm_endpoint')}
                  placeholder={
                    formData.llm_provider === 'local'
                      ? "http://localhost:11434/v1"
                      : formData.llm_provider === 'openrouter'
                      ? "https://openrouter.ai/api/v1"
                      : "https://api.custom-llm.com/v1"
                  }
                  helperText={
                    formData.llm_provider === 'local'
                      ? "Ollama endpoint (default: http://localhost:11434/v1)"
                      : formData.llm_provider === 'openrouter'
                      ? "OpenRouter endpoint (default: https://openrouter.ai/api/v1)"
                      : "Leave empty to use default endpoint for provider"
                  }
                />
              </Grid>
            </Grid>

            <Box mt={4} display="flex" gap={2} flexWrap="wrap">
              <Button
                type="submit"
                variant="contained"
                startIcon={<Save />}
                disabled={loading}
              >
                {loading ? <CircularProgress size={24} /> : 'Save Configuration'}
              </Button>
              <Button
                variant="outlined"
                startIcon={<CheckCircle />}
                onClick={async () => {
                  // Test API connection
                  if (!formData.base_url || !formData.base_url.trim()) {
                    alert('❌ Please enter a Base URL first');
                    return;
                  }
                  
                  try {
                    const response = await api.post(`/config/${projectId}/test-api`, {
                      base_url: formData.base_url,
                      auth_type: formData.auth_type || undefined,
                      auth_username: formData.auth_username || undefined,
                      auth_password: formData.auth_password || undefined,
                      auth_token: formData.auth_token || undefined,
                      auth_key_name: formData.auth_key_name || undefined,
                      auth_key_value: formData.auth_key_value || undefined,
                      oauth2_client_id: formData.oauth2_client_id || undefined,
                      oauth2_client_secret: formData.oauth2_client_secret || undefined,
                      oauth2_token_url: formData.oauth2_token_url || undefined,
                      oauth2_authorization_url: formData.oauth2_authorization_url || undefined,
                      oauth2_scope: formData.oauth2_scope || undefined,
                      oauth2_grant_type: formData.oauth2_grant_type || undefined,
                    });
                    alert(`✅ API Connection Successful!\n\n${response.data.message || 'API connection is working.'}\n\nBase URL: ${response.data.base_url}\nTest URL: ${response.data.test_url}\nStatus Code: ${response.data.status_code}\nAuth Type: ${response.data.auth_type}\nAuth Status: ${response.data.auth_status}`);
                  } catch (error: any) {
                    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || 'Unknown error';
                    alert(`❌ API Connection Failed:\n\n${errorMsg}`);
                  }
                }}
                disabled={loading || !formData.base_url}
              >
                Test API Connection
              </Button>
              <Button
                variant="outlined"
                startIcon={<CheckCircle />}
                onClick={async () => {
                  // Test LLM connection
                  try {
                    const response = await api.post(`/config/${projectId}/test-llm`, {
                      llm_provider: formData.llm_provider,
                      llm_api_key: formData.llm_api_key || undefined,
                      llm_endpoint: formData.llm_endpoint || undefined,
                      llm_model: formData.llm_model || 'gpt-4',
                    });
                    alert(`✅ LLM Connection Successful!\n\n${response.data.message || 'LLM connection is working.'}\n\nProvider: ${response.data.provider}\nEndpoint: ${response.data.endpoint}`);
                  } catch (error: any) {
                    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || 'Unknown error';
                    alert(`❌ LLM Connection Failed:\n\n${errorMsg}`);
                  }
                }}
                disabled={loading || !formData.llm_provider}
              >
                Test LLM Connection
              </Button>
              <Button
                variant="outlined"
                onClick={() => navigate(`/projects/${projectId}`)}
              >
                Cancel
              </Button>
            </Box>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Config;

