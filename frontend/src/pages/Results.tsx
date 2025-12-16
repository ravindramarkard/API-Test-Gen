import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
} from '@mui/material';
import { ExpandMore } from '@mui/icons-material';
import api from '../services/api';

const Results: React.FC = () => {
  const { executionId } = useParams<{ executionId: string }>();
  const [execution, setExecution] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [requests, setRequests] = useState<Array<{url: string, method: string, request: any, response: any, timestamp: string}>>([]);
  const [issueDialogOpen, setIssueDialogOpen] = useState(false);
  const [issueProvider, setIssueProvider] = useState<'jira' | 'github'>('jira');
  const [issueTitle, setIssueTitle] = useState('');
  const [issueDescription, setIssueDescription] = useState('');
  const [issueCreating, setIssueCreating] = useState(false);
  const [issueCreatedUrl, setIssueCreatedUrl] = useState<string | null>(null);
  const [selectedTestIndex, setSelectedTestIndex] = useState<number | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (executionId) {
      // Try SSE first, fallback to polling
      setupSSE();
      
      return () => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
      };
    }
  }, [executionId]);

  const setupSSE = () => {
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
    const sseUrl = `${apiUrl}/execute/${executionId}/stream`;
    
    console.log('🔌 Connecting to SSE:', sseUrl);
    
    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('📥 SSE Message received:', data);
        
        setExecution(data);
        setLoading(false);
        
        // Track requests/responses
        if (data.results && data.results.length > 0) {
          const newRequests = data.results.map((result: any) => ({
            url: `${data.summary?.base_url || ''}${result.endpoint}`,
            method: result.method,
            request: {
              payload: result.payload,
              headers: result.request_headers || {},
            },
            response: {
              status: result.actual_status,
              body: result.response_body,
              headers: result.response_headers || {},
            },
            timestamp: result.completed_at || result.started_at,
          }));
          setRequests(newRequests);
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('❌ SSE Error:', error);
      // Fallback to polling if SSE fails
      eventSource.close();
      startPolling();
    };
    
    eventSource.onopen = () => {
      console.log('✅ SSE Connection opened');
    };
  };

  const startPolling = () => {
    fetchExecution();
    
    const interval = setInterval(() => {
      if (execution?.status === 'running') {
        fetchExecution();
      } else {
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  };

  const fetchExecution = async () => {
    try {
      console.log('📡 Fetching execution:', `/execute/${executionId}`);
      const response = await api.get(`/execute/${executionId}`);
      console.log('📥 Response:', response.data);
      
      setExecution(response.data);
      setLoading(false);
      
      // Track requests/responses
      if (response.data.results && response.data.results.length > 0) {
        const newRequests = response.data.results.map((result: any) => ({
          url: `${response.data.summary?.base_url || ''}${result.endpoint}`,
          method: result.method,
          request: {
            payload: result.payload,
            headers: result.request_headers || {},
          },
          response: {
            status: result.actual_status,
            body: result.response_body,
            headers: result.response_headers || {},
          },
          timestamp: result.completed_at || result.started_at,
        }));
        setRequests(newRequests);
      }
      
      if (response.data.status === 'running') {
        // Continue polling
      }
    } catch (error: any) {
      console.error('❌ Fetch error:', error);
      setLoading(false);
    }
  };

  const handleOpenIssueDialog = (testIndex: number) => {
    setSelectedTestIndex(testIndex);
    const result = execution?.results?.[testIndex];
    if (result) {
      const defaultTitle = `[API Test Failure] ${result.method} ${result.endpoint}`;
      setIssueTitle(defaultTitle);
      const defaultDesc = `Auto-generated issue for failed test.\n\nTest Name: ${result.test_name}\nEndpoint: ${result.method} ${result.endpoint}\nExpected: ${result.expected_status?.join(', ')}\nActual: ${result.actual_status}\n\nYou can edit this description before creating the issue. The backend will attach full request/response trace.`;
      setIssueDescription(defaultDesc);
    } else {
      setIssueTitle('');
      setIssueDescription('');
    }
    setIssueCreatedUrl(null);
    setIssueDialogOpen(true);
  };

  const handleCreateIssue = async () => {
    if (!execution || selectedTestIndex === null) return;
    try {
      setIssueCreating(true);
      setIssueCreatedUrl(null);
      const payload = {
        project_id: execution.project_id || execution.projectId || execution.projectID,
        test_suite_id: execution.test_suite_id || execution.testSuiteId,
        test_execution_id: execution.execution_id,
        test_index: selectedTestIndex,
        provider: issueProvider,
        title: issueTitle || undefined,
        description: issueDescription || undefined,
      };
      const response = await api.post('/integrations/issues', payload);
      setIssueCreatedUrl(response.data.issue_url);
    } catch (error: any) {
      const msg = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`Failed to create issue: ${msg}`);
    } finally {
      setIssueCreating(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!execution) {
    return <Alert severity="error">Execution not found</Alert>;
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'success';
      case 'failed':
        return 'error';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const renderTrace = (trace: any[] | undefined) => {
    if (!trace || trace.length === 0) return null;
    return (
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Trace
        </Typography>
        {trace.map((step, idx) => (
          <Box key={idx} sx={{ mb: 1.5, p: 1, bgcolor: 'grey.50', borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
              <Chip label={`Step ${step.step || idx + 1}`} size="small" />
              <Chip label={step.method} size="small" color="info" />
              <Typography variant="body2" fontFamily="monospace">
                {step.url || step.endpoint}
              </Typography>
              <Chip label={step.response_status} size="small" color={getStatusColor(step.response_status === 200 ? 'passed' : (step.response_status >=200 && step.response_status <300 ? 'passed' : 'failed')) as any} />
            </Box>
            <Typography variant="caption" color="textSecondary">
              Request
            </Typography>
            <Box component="pre" sx={{ bgcolor: 'white', p: 1, borderRadius: 1, fontSize: '0.75rem', overflow: 'auto', mb: 1 }}>
              {JSON.stringify({
                url: step.url || step.endpoint,
                headers: step.request_headers,
                query: step.request_query,
                body: step.request_payload || step.request_body,
              }, null, 2)}
            </Box>
            <Typography variant="caption" color="textSecondary">
              Response
            </Typography>
            <Box component="pre" sx={{ bgcolor: 'white', p: 1, borderRadius: 1, fontSize: '0.75rem', overflow: 'auto' }}>
              {JSON.stringify({
                status: step.response_status,
                headers: step.response_headers,
                body: step.response_body,
              }, null, 2)}
            </Box>
          </Box>
        ))}
      </Box>
    );
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Test Execution Results
      </Typography>

      {execution.status === 'running' && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Tests are running... Updates via Server-Sent Events (SSE)
        </Alert>
      )}

      {execution.summary && (
        <Card sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Summary
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap">
              <Chip label={`Total: ${execution.summary.total}`} />
              <Chip
                label={`Passed: ${execution.summary.passed}`}
                color="success"
              />
              <Chip
                label={`Failed: ${execution.summary.failed}`}
                color="error"
              />
              {execution.summary.errors > 0 && (
                <Chip
                  label={`Errors: ${execution.summary.errors}`}
                  color="error"
                />
              )}
              {execution.summary.progress && (
                <Chip
                  label={`Progress: ${execution.summary.progress}/${execution.summary.total}`}
                />
              )}
            </Box>
            {execution.summary.total > 0 && (
              <Box mt={2}>
                <LinearProgress
                  variant="determinate"
                  value={
                    execution.summary.progress
                      ? (execution.summary.progress / execution.summary.total) * 100
                      : (execution.summary.passed / execution.summary.total) * 100
                  }
                  sx={{ height: 10, borderRadius: 5 }}
                />
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {execution.results && execution.results.length > 0 && (
        <>
          <Typography variant="h6" gutterBottom>
            Test Results
          </Typography>
          <TableContainer component={Paper} sx={{ mb: 4 }}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Test Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Endpoint</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Expected</TableCell>
                  <TableCell>Actual</TableCell>
                  <TableCell>Details</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {execution.results.map((result: any, index: number) => (
                  <TableRow key={index}>
                    <TableCell>{result.test_name}</TableCell>
                    <TableCell>
                      <Chip label={result.test_type} size="small" />
                    </TableCell>
                    <TableCell>
                      {result.method} {result.endpoint}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={result.status}
                        color={getStatusColor(result.status) as any}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{result.expected_status?.join(', ')}</TableCell>
                    <TableCell>{result.actual_status || 'N/A'}</TableCell>
                    <TableCell>
                      <Accordion>
                        <AccordionSummary expandIcon={<ExpandMore />}>
                          <Typography variant="caption">Request/Response & Trace</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Box>
                            <Typography variant="subtitle2" gutterBottom>
                              Request:
                            </Typography>
                            <Box component="pre" sx={{ bgcolor: 'grey.100', p: 1, borderRadius: 1, fontSize: '0.75rem', overflow: 'auto' }}>
                              {JSON.stringify({
                                method: result.method,
                                url: result.endpoint,
                                payload: result.payload,
                              }, null, 2)}
                            </Box>
                            <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                              Response:
                            </Typography>
                            <Box component="pre" sx={{ bgcolor: 'grey.100', p: 1, borderRadius: 1, fontSize: '0.75rem', overflow: 'auto' }}>
                              {JSON.stringify({
                                status: result.actual_status,
                                body: result.response_body?.substring(0, 500),
                                headers: result.response_headers,
                              }, null, 2)}
                            </Box>
                            {renderTrace(result.trace)}
                            {result.error && (
                              <Alert severity="error" sx={{ mt: 1 }}>
                                {result.error}
                              </Alert>
                            )}
                            {result.status !== 'passed' && (
                              <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={() => handleOpenIssueDialog(index)}
                                >
                                  Create Jira/GitHub Issue
                                </Button>
                              </Box>
                            )}
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {execution.error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {execution.error}
        </Alert>
      )}
      <Dialog
        open={issueDialogOpen}
        onClose={() => setIssueDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create External Issue</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <FormControl fullWidth>
              <InputLabel>Provider</InputLabel>
              <Select
                label="Provider"
                value={issueProvider}
                onChange={(e) => setIssueProvider(e.target.value as 'jira' | 'github')}
              >
                <MenuItem value="jira">Jira</MenuItem>
                <MenuItem value="github">GitHub</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Title"
              fullWidth
              value={issueTitle}
              onChange={(e) => setIssueTitle(e.target.value)}
            />
            <TextField
              label="Description"
              fullWidth
              multiline
              minRows={4}
              value={issueDescription}
              onChange={(e) => setIssueDescription(e.target.value)}
            />
            {issueCreatedUrl && (
              <Alert severity="success">
                Issue created.{' '}
                <a href={issueCreatedUrl} target="_blank" rel="noreferrer">
                  Open in {issueProvider === 'jira' ? 'Jira' : 'GitHub'}
                </a>
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIssueDialogOpen(false)}>Close</Button>
          <Button
            onClick={handleCreateIssue}
            disabled={issueCreating}
            variant="contained"
          >
            {issueCreating ? 'Creating…' : 'Create Issue'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Results;
