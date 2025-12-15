import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  TextField,
  Checkbox,
  FormControlLabel,
  InputAdornment,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { Settings, PlayArrow, Visibility, Search, SelectAll, Deselect } from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../hooks/redux';
import { fetchProject } from '../store/slices/projectsSlice';
import { generateTests, executeTests, fetchLatestTestSuite } from '../store/slices/testSlice';
import api from '../services/api';

const ProjectDetail: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { currentProject, loading } = useAppSelector((state) => state.projects);
  const { testSuite, loading: testLoading } = useAppSelector((state) => state.tests);
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [generatedEndpoints, setGeneratedEndpoints] = useState<Set<string>>(new Set());
  const [allTestCases, setAllTestCases] = useState<any[]>([]);

  useEffect(() => {
    if (projectId) {
      dispatch(fetchProject(projectId));
      // Fetch existing test suite if available
      dispatch(fetchLatestTestSuite(projectId));
      // Fetch generated endpoints
      fetchGeneratedEndpoints();
    }
  }, [dispatch, projectId]);

  // Get endpoint key for selection tracking
  const getEndpointKey = (endpoint: { path: string; method: string }) => {
    return `${endpoint.method.toUpperCase()}:${endpoint.path}`;
  };

  const fetchGeneratedEndpoints = async () => {
    if (!projectId) return;
    try {
      const response = await api.get(`/generate/project/${projectId}/generated-endpoints`);
      const generated = response.data.generated_endpoints || [];
      const generatedKeys = new Set<string>(
        generated.map((ep: { path: string; method: string }) => 
          `${ep.method.toUpperCase()}:${ep.path}`
        )
      );
      setGeneratedEndpoints(generatedKeys);
    } catch (error) {
      console.error('Failed to fetch generated endpoints:', error);
      setGeneratedEndpoints(new Set<string>());
    }
  };

  // Filter endpoints based on search query and exclude generated endpoints
  const filteredEndpoints = useMemo(() => {
    if (!currentProject?.endpoints) return [];
    
    // First filter out generated endpoints
    let availableEndpoints = currentProject.endpoints.filter(endpoint => {
      const endpointKey = getEndpointKey(endpoint);
      return !generatedEndpoints.has(endpointKey);
    });
    
    // Then apply search filter
    if (!searchQuery.trim()) return availableEndpoints;
    
    const query = searchQuery.toLowerCase();
    return availableEndpoints.filter(endpoint => 
      endpoint.path.toLowerCase().includes(query) ||
      endpoint.method.toLowerCase().includes(query) ||
      (endpoint.summary && endpoint.summary.toLowerCase().includes(query)) ||
      (endpoint.operation_id && endpoint.operation_id.toLowerCase().includes(query))
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.endpoints, searchQuery, generatedEndpoints]);

  const handleToggleEndpoint = (endpoint: { path: string; method: string }) => {
    const key = getEndpointKey(endpoint);
    const newSelected = new Set(selectedEndpoints);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelectedEndpoints(newSelected);
  };

  const handleSelectAll = () => {
    const allKeys = new Set(filteredEndpoints.map(ep => getEndpointKey(ep)));
    setSelectedEndpoints(allKeys);
  };

  const handleDeselectAll = () => {
    setSelectedEndpoints(new Set());
  };

  const handleGenerateTests = async () => {
    if (projectId) {
      // If endpoints are selected, send them; otherwise generate for all
      const endpointsToGenerate = selectedEndpoints.size > 0
        ? Array.from(selectedEndpoints).map(key => {
            const [method, path] = key.split(':');
            return { method, path };
          })
        : undefined;

      await dispatch(generateTests({ 
        projectId, 
        format: 'pytest',
        selectedEndpoints: endpointsToGenerate
      }));
      
      // Refresh generated endpoints list and clear selection
      await fetchGeneratedEndpoints();
      setSelectedEndpoints(new Set());
      setTabValue(1);
    }
  };

  // Listen for endpoint deletion events from test suite
  useEffect(() => {
    const handleEndpointDeleted = () => {
      fetchGeneratedEndpoints();
    };
    
    window.addEventListener('endpointDeleted', handleEndpointDeleted);
    return () => {
      window.removeEventListener('endpointDeleted', handleEndpointDeleted);
    };
  }, []);

  // Load all test cases for the latest suite so the Test Suite tab can show them
  useEffect(() => {
    const loadTestCases = async () => {
      if (!testSuite?.test_suite_id) {
        setAllTestCases([]);
        return;
      }
      try {
        const res = await api.get(`/generate/${testSuite.test_suite_id}/cases`);
        const data = res.data;
        const cases = data.all_test_cases || data.all_tests || [];
        setAllTestCases(cases);
      } catch (err) {
        console.error('Failed to load test cases', err);
        setAllTestCases([]);
      }
    };
    loadTestCases();
  }, [testSuite?.test_suite_id]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!currentProject) {
    return (
      <Alert severity="error">Project not found</Alert>
    );
  }

  const handleTabChange = (_: any, newValue: number) => {
    // If user selects "Test Suite" and a suite exists, navigate to the test suite page
    if (newValue === 1 && testSuite?.test_suite_id) {
      navigate(`/test-suites/${testSuite.test_suite_id}`);
      return;
    }
    setTabValue(newValue);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {currentProject.name}
          </Typography>
          <Typography color="textSecondary">
            {currentProject.description || 'No description'}
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<Settings />}
            onClick={() => navigate(`/projects/${projectId}/config`)}
          >
            Configure
          </Button>
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            onClick={handleGenerateTests}
            disabled={testLoading}
          >
            {selectedEndpoints.size > 0 
              ? `Generate Tests (${selectedEndpoints.size} selected)`
              : 'Generate All Tests'}
          </Button>
        </Box>
      </Box>

      <Tabs value={tabValue} onChange={handleTabChange} sx={{ mb: 3 }}>
        <Tab label="Endpoints" />
        <Tab label="Test Suite" />
        <Tab label="Reports" />
      </Tabs>

      {tabValue === 0 && (
        <Box>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <TextField
              placeholder="Search endpoints by path, method, or description..."
              variant="outlined"
              size="small"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
              sx={{ flex: 1, maxWidth: 500 }}
            />
            <Box display="flex" gap={1} ml={2}>
              <Button
                size="small"
                startIcon={<SelectAll />}
                onClick={handleSelectAll}
                disabled={filteredEndpoints.length === 0}
              >
                Select All ({filteredEndpoints.length})
              </Button>
              <Button
                size="small"
                startIcon={<Deselect />}
                onClick={handleDeselectAll}
                disabled={selectedEndpoints.size === 0}
              >
                Deselect All
              </Button>
              <Chip
                label={`${selectedEndpoints.size} selected`}
                color="primary"
                variant="outlined"
              />
            </Box>
          </Box>

          <TableContainer component={Paper} sx={{ maxHeight: '60vh', overflow: 'auto' }}>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" width={50}>
                    <Checkbox
                      indeterminate={
                        selectedEndpoints.size > 0 &&
                        selectedEndpoints.size < filteredEndpoints.length
                      }
                      checked={
                        filteredEndpoints.length > 0 &&
                        filteredEndpoints.every(ep => selectedEndpoints.has(getEndpointKey(ep)))
                      }
                      onChange={(e) => {
                        if (e.target.checked) {
                          handleSelectAll();
                        } else {
                          handleDeselectAll();
                        }
                      }}
                    />
                  </TableCell>
                  <TableCell>Method</TableCell>
                  <TableCell>Path</TableCell>
                  <TableCell>Description</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredEndpoints.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} align="center">
                      <Typography color="textSecondary">
                        {searchQuery ? 'No endpoints found matching your search' : 'No endpoints available'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredEndpoints.map((endpoint, index: number) => {
                    const endpointKey = getEndpointKey(endpoint);
                    const isSelected = selectedEndpoints.has(endpointKey);
                    return (
                      <TableRow
                        key={index}
                        hover
                        onClick={() => handleToggleEndpoint(endpoint)}
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell padding="checkbox">
                          <Checkbox
                            checked={isSelected}
                            onChange={() => handleToggleEndpoint(endpoint)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={endpoint.method}
                            color={
                              endpoint.method === 'GET' ? 'success' :
                              endpoint.method === 'POST' ? 'primary' :
                              endpoint.method === 'PUT' ? 'info' :
                              endpoint.method === 'DELETE' ? 'error' : 'default'
                            }
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace" fontWeight="medium">
                            {endpoint.path}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="textSecondary">
                            {endpoint.summary || endpoint.operation_id || 'No description'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {tabValue === 1 && (
        <Box>
          {testLoading ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : testSuite ? (
            <>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Generated Test Suite
                  </Typography>
                  <Typography variant="body2" color="textSecondary" paragraph>
                    Test Count: {testSuite.test_count}
                  </Typography>
                  {testSuite.tests_by_type && (
                    <Box mb={2}>
                      {Object.entries(testSuite.tests_by_type).map(([type, count]) => (
                        <Chip
                          key={type}
                          label={`${type}: ${count}`}
                          sx={{ mr: 1, mb: 1 }}
                        />
                      ))}
                    </Box>
                  )}
                  <Alert severity="success" sx={{ mb: 2 }}>
                    <Typography variant="body2">
                      <strong>Assertions Generated:</strong> All test cases include automatic assertions based on OpenAPI response schemas:
                    </Typography>
                    <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                      <li>Status code validation</li>
                      <li>Response body existence</li>
                      <li>Required properties in response objects</li>
                      <li>Array structure validation</li>
                      <li>Schema reference validation</li>
                    </Box>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      View and edit assertions in the Test Suite page.
                    </Typography>
                  </Alert>
                  {testSuite.test_suite_id && (
                    <Box display="flex" gap={2} flexWrap="wrap">
                      <Button
                        variant="outlined"
                        startIcon={<Visibility />}
                        onClick={() => navigate(`/test-suites/${testSuite.test_suite_id}`)}
                      >
                        View Test Cases
                      </Button>
                      <Button
                        variant="contained"
                        startIcon={<PlayArrow />}
                        onClick={async () => {
                          // Execute all tests
                          try {
                            const response = await api.post(`/execute/${testSuite.test_suite_id}`);
                            if (response.data.execution_id) {
                              // Navigate to execution results
                              navigate(`/executions/${response.data.execution_id}`);
                            } else {
                              alert(`Failed to start execution: ${response.data.detail || 'Unknown error'}`);
                            }
                          } catch (error: any) {
                            const errorMsg = error.response?.data?.detail || error.message || 'Network error';
                            alert(`Failed to execute tests: ${errorMsg}`);
                          }
                        }}
                      >
                        Execute All Tests
                      </Button>
                    </Box>
                  )}
                </CardContent>
              </Card>

              {allTestCases.length > 0 && (
                <Card sx={{ mt: 3 }}>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                      <Typography variant="h6">Generated Test Cases</Typography>
                      <Button
                        variant="outlined"
                        onClick={() => navigate(`/test-suites/${testSuite?.test_suite_id}`)}
                      >
                        Open Test Suite
                      </Button>
                    </Box>
                    <TableContainer component={Paper} sx={{ maxHeight: '60vh', overflow: 'auto' }}>
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            <TableCell>Method</TableCell>
                            <TableCell>Endpoint</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Name</TableCell>
                            <TableCell>Expected Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {allTestCases.map((tc) => (
                            <TableRow key={tc.index}>
                              <TableCell>
                                <Chip
                                  label={tc.method}
                                  size="small"
                                  color={
                                    tc.method === 'GET' ? 'success' :
                                    tc.method === 'POST' ? 'primary' :
                                    tc.method === 'PUT' ? 'info' :
                                    tc.method === 'DELETE' ? 'error' : 'default'
                                  }
                                />
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2" fontFamily="monospace">
                                  {tc.endpoint}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Chip label={tc.type} size="small" variant="outlined" />
                              </TableCell>
                              <TableCell>
                                <Typography variant="body2" fontWeight="medium">
                                  {tc.name}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                <Chip
                                  label={tc.expected_status?.join(', ') || '200'}
                                  size="small"
                                  variant="outlined"
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Alert severity="info">
              No test suite generated yet. Click "Generate Tests" to create one.
            </Alert>
          )}
        </Box>
      )}

      {tabValue === 2 && (
        <Box>
          <Button
            variant="contained"
            onClick={() => navigate(`/reports/project/${projectId}`)}
            sx={{ mb: 2 }}
          >
            View Full Project Reports
          </Button>
          <Alert severity="info">
            Click the button above to view comprehensive project reports including test execution metrics, trends, and analytics.
          </Alert>
        </Box>
      )}
    </Box>
  );
};

export default ProjectDetail;

