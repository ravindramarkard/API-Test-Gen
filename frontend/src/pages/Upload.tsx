import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Divider,
} from '@mui/material';
import { CloudUpload, Link as LinkIcon } from '@mui/icons-material';
import api from '../services/api';

const Upload: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState('');
  const [specUrl, setSpecUrl] = useState('');
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setFile(event.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate project name
    if (!projectName || !projectName.trim()) {
      setError('Project name is required');
      return;
    }

    // Validate based on upload method
    if (uploadMethod === 'file' && !file) {
      setError('Please select a file');
      return;
    }
    
    if (uploadMethod === 'url' && !specUrl.trim()) {
      setError('Please enter a valid URL');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      let response;
      
      if (uploadMethod === 'file') {
        const formData = new FormData();
        formData.append('file', file!);
        formData.append('project_name', projectName.trim());

        const uploadUrl = 'upload';
        response = await api.post(uploadUrl, formData);
      } else {
        // URL-based upload
        const uploadUrl = 'upload/url';
        response = await api.post(uploadUrl, {
          url: specUrl.trim(),
          project_name: projectName.trim()
        });
      }

      setSuccess(`Project "${response.data.name}" created successfully!`);
      
      // Navigate to project detail after a short delay
      setTimeout(() => {
        navigate(`/projects/${response.data.project_id}`);
      }, 1500);
    } catch (err: any) {
      console.error('Upload error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to upload specification';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Upload OpenAPI/Swagger Specification
      </Typography>

      <Card sx={{ maxWidth: 800, mx: 'auto', mt: 4 }}>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Project Name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              margin="normal"
              required
              error={!projectName.trim()}
              helperText={!projectName.trim() ? 'Project name is required' : 'Enter a name for your project'}
            />

            <Box mt={3} mb={2}>
              <Tabs value={uploadMethod} onChange={(_, newValue) => setUploadMethod(newValue)}>
                <Tab label="Upload File" value="file" icon={<CloudUpload />} iconPosition="start" />
                <Tab label="From URL" value="url" icon={<LinkIcon />} iconPosition="start" />
              </Tabs>
            </Box>

            <Divider sx={{ my: 2 }} />

            {uploadMethod === 'file' ? (
              <Box>
                <Box mt={2} mb={2}>
                  <input
                    accept=".json,.yaml,.yml"
                    style={{ display: 'none' }}
                    id="file-upload"
                    type="file"
                    onChange={handleFileChange}
                  />
                  <label htmlFor="file-upload">
                    <Button
                      variant="outlined"
                      component="span"
                      startIcon={<CloudUpload />}
                      fullWidth
                      sx={{ py: 2 }}
                    >
                      {file ? file.name : 'Select OpenAPI/Swagger File'}
                    </Button>
                  </label>
                </Box>

                {file && (
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                    Selected: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                  </Typography>
                )}
              </Box>
            ) : (
              <Box>
                <TextField
                  fullWidth
                  label="OpenAPI/Swagger Specification URL"
                  value={specUrl}
                  onChange={(e) => setSpecUrl(e.target.value)}
                  margin="normal"
                  placeholder="https://example.com/api/openapi.json"
                  helperText="Enter the URL to fetch the OpenAPI/Swagger specification (JSON or YAML)"
                />
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {success && (
              <Alert severity="success" sx={{ mb: 2 }}>
                {success}
              </Alert>
            )}

            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={!projectName.trim() || (uploadMethod === 'file' && !file) || (uploadMethod === 'url' && !specUrl.trim()) || loading}
              sx={{ mt: 2 }}
            >
              {loading ? <CircularProgress size={24} /> : uploadMethod === 'file' ? 'Upload and Parse' : 'Fetch and Parse'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Box mt={4}>
        <Typography variant="h6" gutterBottom>
          Supported Formats
        </Typography>
        <Typography variant="body2" color="textSecondary">
          • OpenAPI 3.x (JSON/YAML)
          <br />
          • Swagger 2.0 (JSON/YAML)
          <br />
          • Files with $ref references are automatically resolved
        </Typography>
      </Box>
    </Box>
  );
};

export default Upload;
