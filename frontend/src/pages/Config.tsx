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
  
  const [llmKeyMasked, setLlmKeyMasked] = useState(true); // Track if showing masked value
  const [llmKeyPlaceholder, setLlmKeyPlaceholder] = useState(''); // Placeholder for masked key

  const [integrationProvider, setIntegrationProvider] = useState<'jira' | 'github'>('jira');
  const [integrationBaseUrl, setIntegrationBaseUrl] = useState('');
  const [integrationProjectKey, setIntegrationProjectKey] = useState('');
  const [integrationRepoOwner, setIntegrationRepoOwner] = useState('');
  const [integrationRepoName, setIntegrationRepoName] = useState('');
  const [integrationToken, setIntegrationToken] = useState('');
  const [hasExistingIntegrationToken, setHasExistingIntegrationToken] = useState(false);

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
      
      // Set masked placeholder if key exists
      if (config.has_llm_key) {
        // Generate masked placeholder based on provider
        const currentProvider = formData.llm_provider || config.llm_provider || 'openai';
        const maskedValue = currentProvider === 'openai' || currentProvider === 'openrouter' 
          ? 'sk-••••••••••••••••••••••••••••••••••••' 
          : '••••••••••••••••••••••••••••••••••••';
        setLlmKeyPlaceholder(maskedValue);
        // Keep field empty but show placeholder when masked
        if (llmKeyMasked) {
          setFormData((prev) => ({ ...prev, llm_api_key: '' }));
        }
      } else {
        setLlmKeyPlaceholder('');
        setLlmKeyMasked(true);
      }
    }
  }, [config, llmKeyMasked, formData.llm_provider]);

  // Load existing integration configuration for this project (non-sensitive)
  useEffect(() => {
    const loadIntegrations = async () => {
      if (!projectId) return;
      try {
        const res = await api.get(`/integrations/config/${projectId}`);
        const items = res.data as Array<{
          provider: string;
          base_url?: string;
          project_key?: string;
          repo_owner?: string;
          repo_name?: string;
          has_token: boolean;
        }>;
        if (items && items.length > 0) {
          const jira = items.find((i) => i.provider === 'jira');
          const gh = items.find((i) => i.provider === 'github');
          const initial = jira || gh || items[0];
          if (initial) {
            const prov = (initial.provider as 'jira' | 'github') || 'jira';
            setIntegrationProvider(prov);
            setIntegrationBaseUrl(initial.base_url || '');
            setIntegrationProjectKey(initial.project_key || '');
            setIntegrationRepoOwner(initial.repo_owner || '');
            setIntegrationRepoName(initial.repo_name || '');
            setHasExistingIntegrationToken(initial.has_token);
            setIntegrationToken('');
          }
        } else {
          setHasExistingIntegrationToken(false);
          setIntegrationToken('');
          setIntegrationBaseUrl('');
          setIntegrationProjectKey('');
          setIntegrationRepoOwner('');
          setIntegrationRepoName('');
        }
      } catch (err) {
        console.error('Failed to load integration config', err);
      }
    };
    loadIntegrations();
  }, [projectId]);

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
      // If field is empty and key exists, don't send llm_api_key (keep existing)
      const configToSave = { ...formData };
      if (!formData.llm_api_key && config?.has_llm_key) {
        // Don't include llm_api_key in the save request - backend will keep existing
        delete (configToSave as any).llm_api_key;
      }
      
      await dispatch(saveConfig({ projectId, config: configToSave }));
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
              Integrations (Jira / GitHub Issues)
            </Typography>
            <Alert severity="info" sx={{ mb: 2 }}>
              Configure an issue tracker to create Jira/GitHub issues directly from failed tests.
            </Alert>
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth>
                  <InputLabel>Provider</InputLabel>
                  <Select
                    label="Provider"
                    value={integrationProvider}
                    onChange={(e) =>
                      setIntegrationProvider(e.target.value as 'jira' | 'github')
                    }
                  >
                    <MenuItem value="jira">Jira</MenuItem>
                    <MenuItem value="github">GitHub</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Base URL"
                  value={integrationBaseUrl}
                  onChange={(e) => setIntegrationBaseUrl(e.target.value)}
                  placeholder={
                    integrationProvider === 'jira'
                      ? 'https://your-domain.atlassian.net'
                      : 'https://api.github.com'
                  }
                  helperText={
                    integrationProvider === 'jira'
                      ? 'Your Jira cloud or server base URL'
                      : 'GitHub API base URL (usually https://api.github.com)'
                  }
                />
              </Grid>
              {integrationProvider === 'jira' ? (
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Jira Project Key"
                    value={integrationProjectKey}
                    onChange={(e) => setIntegrationProjectKey(e.target.value)}
                    placeholder="ABC"
                    helperText="Key of the Jira project where bugs will be created"
                  />
                </Grid>
              ) : (
                <>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="GitHub Repo Owner"
                      value={integrationRepoOwner}
                      onChange={(e) => setIntegrationRepoOwner(e.target.value)}
                      placeholder="your-org-or-user"
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="GitHub Repo Name"
                      value={integrationRepoName}
                      onChange={(e) => setIntegrationRepoName(e.target.value)}
                      placeholder="your-repo"
                    />
                  </Grid>
                </>
              )}
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label={
                    integrationProvider === 'jira'
                      ? 'Jira API Token / PAT'
                      : 'GitHub Personal Access Token'
                  }
                  type="password"
                  value={integrationToken}
                  onChange={(e) => setIntegrationToken(e.target.value)}
                  helperText={
                    hasExistingIntegrationToken
                      ? 'Token already stored. Leave empty to keep existing, or enter a new token to replace.'
                      : integrationProvider === 'jira'
                      ? 'API token for a Jira user with permission to create issues.'
                      : 'GitHub PAT with repo:issues permission.'
                  }
                />
              </Grid>
              <Grid item xs={12}>
                <Button
                  variant="outlined"
                  onClick={async () => {
                    if (!projectId) return;
                    try {
                      const payload: any = {
                        provider: integrationProvider,
                        base_url: integrationBaseUrl || undefined,
                      };
                      if (integrationProvider === 'jira') {
                        payload.project_key = integrationProjectKey || undefined;
                      } else {
                        payload.repo_owner = integrationRepoOwner || undefined;
                        payload.repo_name = integrationRepoName || undefined;
                      }
                      if (integrationToken) {
                        payload.auth_token = integrationToken;
                      }
                      await api.post(`/integrations/config/${projectId}`, payload);
                      alert('✅ Integration configuration saved');
                      setIntegrationToken('');
                      setHasExistingIntegrationToken(true);
                    } catch (error: any) {
                      const msg =
                        error.response?.data?.detail ||
                        error.response?.data?.message ||
                        error.message ||
                        'Unknown error';
                      alert(`❌ Failed to save integration config:\n\n${msg}`);
                    }
                  }}
                >
                  Save Integration
                </Button>
              </Grid>
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
                  type={llmKeyMasked && config?.has_llm_key ? "text" : "password"}
                  value={llmKeyMasked && config?.has_llm_key ? llmKeyPlaceholder : formData.llm_api_key}
                  onChange={(e) => {
                    // If user starts typing, switch to password mode and clear placeholder
                    if (llmKeyMasked && config?.has_llm_key) {
                      setLlmKeyMasked(false);
                      setFormData((prev) => ({ ...prev, llm_api_key: e.target.value }));
                    } else {
                      handleChange('llm_api_key')(e);
                    }
                  }}
                  onFocus={() => {
                    // When focused, if showing masked value, switch to edit mode
                    if (llmKeyMasked && config?.has_llm_key) {
                      setLlmKeyMasked(false);
                      setFormData((prev) => ({ ...prev, llm_api_key: '' }));
                    }
                  }}
                  onBlur={() => {
                    // If field is empty after blur and key exists, show masked again
                    if (!formData.llm_api_key && config?.has_llm_key) {
                      setLlmKeyMasked(true);
                    }
                  }}
                  helperText={
                    formData.llm_provider === 'local'
                      ? "Not required for local Ollama (leave empty)"
                      : config?.has_llm_key
                        ? llmKeyMasked
                          ? "Key stored (encrypted). Click to edit or leave empty to keep existing."
                          : "Key on file. Leave empty to keep existing, enter to replace."
                        : formData.llm_provider === 'openrouter'
                          ? "Your OpenRouter API key (get from https://openrouter.ai)"
                          : "Your API key for the selected LLM provider"
                  }
                  disabled={formData.llm_provider === 'local'}
                  InputProps={{
                    readOnly: llmKeyMasked && config?.has_llm_key,
                    style: llmKeyMasked && config?.has_llm_key ? { 
                      fontFamily: 'monospace',
                      color: '#666'
                    } : {}
                  }}
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
                    // If field is empty or showing masked value, don't send key (backend will use stored one)
                    // Only send the key if user explicitly entered a new one
                    const apiKeyToSend = (llmKeyMasked && config?.has_llm_key) || !formData.llm_api_key || formData.llm_api_key.trim() === ''
                      ? undefined 
                      : formData.llm_api_key;
                    
                    // Build request payload - only include fields that have values
                    const testPayload: any = {
                      llm_provider: formData.llm_provider || 'openai',
                      llm_model: formData.llm_model || 'gpt-4',
                    };
                    
                    // Only include API key if user provided a new one
                    if (apiKeyToSend) {
                      testPayload.llm_api_key = apiKeyToSend;
                    }
                    
                    // Only include endpoint if provided
                    if (formData.llm_endpoint && formData.llm_endpoint.trim()) {
                      testPayload.llm_endpoint = formData.llm_endpoint;
                    }
                    
                    const response = await api.post(`/config/${projectId}/test-llm`, testPayload);
                    alert(`✅ LLM Connection Successful!\n\n${response.data.message || 'LLM connection is working.'}\n\nProvider: ${response.data.provider}\nEndpoint: ${response.data.endpoint}`);
                  } catch (error: any) {
                    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || 'Unknown error';
                    
                    // If decryption failed, prompt user to re-enter the key
                    if (errorMsg.includes('decrypt') || errorMsg.includes('decryption')) {
                      const shouldReenter = window.confirm(
                        `❌ LLM Connection Failed:\n\n${errorMsg}\n\nWould you like to re-enter your LLM API key?`
                      );
                      if (shouldReenter) {
                        // Unmask the field so user can enter new key
                        setLlmKeyMasked(false);
                        setFormData((prev) => ({ ...prev, llm_api_key: '' }));
                        // Focus on the LLM API key field
                        setTimeout(() => {
                          const keyField = document.querySelector('input[type="password"][label*="LLM API Key"]') as HTMLInputElement;
                          if (keyField) keyField.focus();
                        }, 100);
                      }
                    } else {
                      alert(`❌ LLM Connection Failed:\n\n${errorMsg}`);
                    }
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

