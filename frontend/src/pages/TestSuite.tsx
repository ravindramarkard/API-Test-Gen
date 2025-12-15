import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Checkbox,
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
  IconButton,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Breadcrumbs,
  Link,
  InputAdornment,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  PlayArrow,
  SelectAll,
  Deselect,
  Visibility,
  ExpandMore,
  Edit,
  CheckCircle,
  Cancel,
  Home,
  Folder,
  Delete,
  Search,
  ViewList,
  ViewModule,
} from '@mui/icons-material';
import api from '../services/api';

interface Assertion {
  type: 'status_code' | 'response_body' | 'response_header' | 'response_time' | 'custom';
  condition: string; // e.g., "equals", "contains", "greater_than", "less_than", "matches"
  expected_value?: any;
  field?: string; // For response_body or response_header assertions
  description?: string;
}

interface TestCase {
  index: number;
  type: string;
  name: string;
  endpoint: string;
  method: string;
  description?: string;
  payload?: any;
  expected_status?: number[];
  assertions?: Assertion[];
}

interface TestSuiteData {
  test_suite_id: string;
  name?: string;
  test_count: number;
  tests_by_type?: Record<string, TestCase[]>;
  test_cases_by_type?: Record<string, TestCase[]>;
  all_tests?: TestCase[];
  all_test_cases?: TestCase[];
  project_id?: string;
  project_name?: string;
}

const TestSuite: React.FC = () => {
  const { testSuiteId } = useParams<{ testSuiteId: string }>();
  const navigate = useNavigate();
  const [testSuite, setTestSuite] = useState<TestSuiteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectInfo, setProjectInfo] = useState<{ id: string; name: string } | null>(null);
  const [selectedTests, setSelectedTests] = useState<Set<number>>(new Set());
  const [deletingEndpoint, setDeletingEndpoint] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [expandedEndpoints, setExpandedEndpoints] = useState<Set<string>>(new Set());
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingTestCase, setEditingTestCase] = useState<TestCase | null>(null);
  const [editedPayload, setEditedPayload] = useState<string>('');
  const [editedHeaders, setEditedHeaders] = useState<string>('');
  const [editedAssertions, setEditedAssertions] = useState<Assertion[]>([]);
  const [runningTest, setRunningTest] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [resultDialogOpen, setResultDialogOpen] = useState(false);
  const [assertionDialogOpen, setAssertionDialogOpen] = useState(false);
  const [editingAssertion, setEditingAssertion] = useState<Assertion | null>(null);
  const [assertionIndex, setAssertionIndex] = useState<number>(-1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grouped' | 'list'>('grouped');
  const [deletingAll, setDeletingAll] = useState(false);

  useEffect(() => {
    if (testSuiteId) {
      fetchTestCases();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testSuiteId]);

  const fetchTestCases = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/generate/${testSuiteId}/cases`);
      const data = response.data;
      
      // Normalize the response - handle both test_cases_by_type and tests_by_type
      const normalizedData: TestSuiteData = {
        test_suite_id: data.test_suite_id || data.test_suite_id,
        name: data.name,
        test_count: data.test_count || 0,
        tests_by_type: data.test_cases_by_type || data.tests_by_type || {},
        all_tests: data.all_test_cases || data.all_tests || [],
        project_id: data.project_id,
        project_name: data.project_name
      };
      
      setTestSuite(normalizedData);
      
      // Set project info for breadcrumbs
      if (data.project_id && data.project_name) {
        setProjectInfo({ id: data.project_id, name: data.project_name });
      } else if (data.project_id) {
        // Fetch project name if not provided
        try {
          const projectResponse = await api.get(`/projects/${data.project_id}`);
          setProjectInfo({ id: data.project_id, name: projectResponse.data.name });
        } catch (error) {
          console.error('Failed to fetch project info:', error);
        }
      }
      
      // Initialize with all tests selected
      if (normalizedData.all_tests && normalizedData.all_tests.length > 0) {
        const allIndices = normalizedData.all_tests.map((t: TestCase) => t.index);
        setSelectedTests(new Set(allIndices));
        
        // Expand all endpoints by default
        const allEndpointKeys = new Set(
          normalizedData.all_tests.map((t: TestCase) => `${t.method}:${t.endpoint}`)
        );
        setExpandedEndpoints(allEndpointKeys);
      }
    } catch (error: any) {
      console.error('Failed to fetch test cases:', error);
    } finally {
      setLoading(false);
    }
  };

  // Group test cases by endpoint, then by type
  const testCasesByEndpoint = useMemo(() => {
    if (!testSuite) return {};
    
    const allTests = testSuite.all_tests || testSuite.all_test_cases || [];
    let filteredTests = allTests;
    
    // Apply search filter if search query exists
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filteredTests = allTests.filter((testCase: TestCase) => {
        const endpointMatch = testCase.endpoint?.toLowerCase().includes(query);
        const methodMatch = testCase.method?.toLowerCase().includes(query);
        const nameMatch = testCase.name?.toLowerCase().includes(query);
        const typeMatch = testCase.type?.toLowerCase().includes(query);
        const descriptionMatch = testCase.description?.toLowerCase().includes(query);
        return endpointMatch || methodMatch || nameMatch || typeMatch || descriptionMatch;
      });
    }
    
    const grouped: Record<string, Record<string, TestCase[]>> = {};
    
    filteredTests.forEach((testCase: TestCase) => {
      const endpointKey = `${testCase.method}:${testCase.endpoint}`;
      
      if (!grouped[endpointKey]) {
        grouped[endpointKey] = {};
      }
      
      const testType = testCase.type || 'unknown';
      if (!grouped[endpointKey][testType]) {
        grouped[endpointKey][testType] = [];
      }
      
      grouped[endpointKey][testType].push(testCase);
    });
    
    return grouped;
  }, [testSuite, searchQuery]);

  const handleToggleEndpoint = (endpointKey: string) => {
    const newExpanded = new Set(expandedEndpoints);
    if (newExpanded.has(endpointKey)) {
      newExpanded.delete(endpointKey);
    } else {
      newExpanded.add(endpointKey);
    }
    setExpandedEndpoints(newExpanded);
  };

  const handleSelectTest = (index: number) => {
    const newSelected = new Set(selectedTests);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedTests(newSelected);
  };

  const handleSelectAll = () => {
    if (!testSuite) return;
    const allTests = testSuite.all_tests || testSuite.all_test_cases || [];
    const allIndices = new Set(allTests.map((t: TestCase) => t.index));
    setSelectedTests(allIndices);
  };

  const handleDeselectAll = () => {
    setSelectedTests(new Set());
  };

  const handleSelectEndpoint = (endpointKey: string) => {
    const endpointTests = testCasesByEndpoint[endpointKey] || {};
    const allTestsInEndpoint: TestCase[] = [];
    Object.values(endpointTests).forEach(typeTests => {
      allTestsInEndpoint.push(...typeTests);
    });
    
    const allIndices = new Set(allTestsInEndpoint.map(t => t.index));
    const newSelected = new Set(selectedTests);
    
    // If all are selected, deselect; otherwise select all
    const allSelected = allIndices.size > 0 && Array.from(allIndices).every(idx => newSelected.has(idx));
    if (allSelected) {
      allIndices.forEach(idx => newSelected.delete(idx));
    } else {
      allIndices.forEach(idx => newSelected.add(idx));
    }
    
    setSelectedTests(newSelected);
  };

  const handleSelectType = (endpointKey: string, type: string) => {
    const typeTests = testCasesByEndpoint[endpointKey]?.[type] || [];
    const typeIndices = new Set(typeTests.map(t => t.index));
    const newSelected = new Set(selectedTests);
    
    // If all are selected, deselect; otherwise select all
    const allSelected = typeIndices.size > 0 && Array.from(typeIndices).every(idx => newSelected.has(idx));
    if (allSelected) {
      typeIndices.forEach(idx => newSelected.delete(idx));
    } else {
      typeIndices.forEach(idx => newSelected.add(idx));
    }
    
    setSelectedTests(newSelected);
  };

  const handleExecuteSelected = async () => {
    if (selectedTests.size === 0) {
      alert('Please select at least one test case to execute');
      return;
    }

    try {
      setExecuting(true);
      const testIndices = Array.from(selectedTests);
      const response = await api.post(`/execute/${testSuiteId}`, { test_indices: testIndices });
      
      if (response.data.execution_id) {
        navigate(`/executions/${response.data.execution_id}`);
      } else {
        alert(`Failed to start execution: ${response.data.detail || 'Unknown error'}`);
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Network error';
      alert(`Failed to execute tests: ${errorMsg}`);
    } finally {
      setExecuting(false);
    }
  };

  const handleDeleteEndpoint = async (endpointKey: string) => {
    if (!testSuiteId || !window.confirm(`Are you sure you want to delete all test cases for ${endpointKey}?`)) {
      return;
    }

    try {
      setDeletingEndpoint(endpointKey);
      const [method, path] = endpointKey.split(':');
      
      const response = await api.delete(`/generate/${testSuiteId}/endpoints`, {
        data: [{ path, method: method.toUpperCase() }]
      });
      
      // Refresh test cases
      await fetchTestCases();
      
      // Trigger event to refresh generated endpoints in parent
      if (projectInfo?.id) {
        window.dispatchEvent(new CustomEvent('endpointDeleted', { 
          detail: { endpoint: { path, method: method.toUpperCase() } } 
        }));
      }
      
      alert(response.data.message || 'Endpoint tests deleted successfully');
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Network error';
      alert(`Failed to delete endpoint tests: ${errorMsg}`);
    } finally {
      setDeletingEndpoint(null);
    }
  };

  const handleDeleteAll = async () => {
    if (!testSuiteId || !window.confirm('Are you sure you want to delete ALL test cases in this suite? This cannot be undone.')) {
      return;
    }
    try {
      setDeletingAll(true);
      const response = await api.delete(`/generate/${testSuiteId}/endpoints`);
      await fetchTestCases();
      // Notify project page to refresh generated endpoints
      if (projectInfo?.id) {
        window.dispatchEvent(new CustomEvent('endpointDeleted', { detail: { endpoint: null } }));
      }
      alert(response.data.message || 'All test cases deleted');
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Network error';
      alert(`Failed to delete all tests: ${errorMsg}`);
    } finally {
      setDeletingAll(false);
    }
  };

  const handleEditTest = (testCase: TestCase) => {
    setEditingTestCase(testCase);
    setEditedPayload(JSON.stringify(testCase.payload || {}, null, 2));
    setEditedHeaders(JSON.stringify((testCase as any).headers || {}, null, 2));
    // Load assertions from test case - these are the generated assertions from OpenAPI schema
    const testCaseAssertions = testCase.assertions || [];
    setEditedAssertions(testCaseAssertions);
    setEditDialogOpen(true);
  };

  const handleCloseEditDialog = () => {
    setEditDialogOpen(false);
    setEditingTestCase(null);
    setEditedPayload('');
    setEditedHeaders('');
    setEditedAssertions([]);
  };

  const handleAddAssertion = () => {
    setEditingAssertion({
      type: 'status_code',
      condition: 'equals',
      expected_value: 200,
      description: '',
    });
    setAssertionIndex(-1);
    setAssertionDialogOpen(true);
  };

  const handleEditAssertion = (assertion: Assertion, index: number) => {
    setEditingAssertion({ ...assertion });
    setAssertionIndex(index);
    setAssertionDialogOpen(true);
  };

  const handleDeleteAssertion = (index: number) => {
    const newAssertions = editedAssertions.filter((_, i) => i !== index);
    setEditedAssertions(newAssertions);
  };

  const handleSaveAssertion = () => {
    if (!editingAssertion) return;
    
    const newAssertions = [...editedAssertions];
    if (assertionIndex >= 0) {
      newAssertions[assertionIndex] = editingAssertion;
    } else {
      newAssertions.push(editingAssertion);
    }
    setEditedAssertions(newAssertions);
    setAssertionDialogOpen(false);
    setEditingAssertion(null);
    setAssertionIndex(-1);
  };

  const handleRunSingleTest = async (testCase: TestCase, useEdited: boolean = false) => {
    if (!testSuiteId) return;

    try {
      setRunningTest(testCase.index);
      
      // Prepare test case with optional modifications
      const testCaseToRun = { ...testCase };
      let modifiedPayload = undefined;
      let modifiedHeaders = undefined;
      let modifiedAssertions = undefined;

      if (useEdited && editingTestCase?.index === testCase.index) {
        try {
          modifiedPayload = editedPayload ? JSON.parse(editedPayload) : undefined;
        } catch (e) {
          alert('Invalid JSON in payload. Using original payload.');
        }
        try {
          modifiedHeaders = editedHeaders ? JSON.parse(editedHeaders) : undefined;
        } catch (e) {
          alert('Invalid JSON in headers. Using original headers.');
        }
        // Use edited assertions if provided, otherwise use original test case assertions
        modifiedAssertions = editedAssertions.length > 0 
          ? editedAssertions 
          : (testCase.assertions && testCase.assertions.length > 0 ? testCase.assertions : undefined);
      } else {
        // If not using edited version, include original assertions if they exist
        if (testCase.assertions && testCase.assertions.length > 0) {
          modifiedAssertions = testCase.assertions;
        }
      }

      const response = await api.post(
        `/execute/single?test_suite_id=${testSuiteId}`,
        {
          test_case: testCaseToRun,
          modified_payload: modifiedPayload,
          modified_headers: modifiedHeaders,
          modified_assertions: modifiedAssertions,
        }
      );

      setTestResult(response.data);
      setResultDialogOpen(true);
      if (useEdited) {
        handleCloseEditDialog();
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Network error';
      alert(`Failed to execute test: ${errorMsg}`);
    } finally {
      setRunningTest(null);
    }
  };

  const getTypeColor = (type: string) => {
    const colors: Record<string, 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'> = {
      happy_path: 'success',
      negative: 'error',
      boundary: 'warning',
      security: 'error',
      performance: 'info',
      validation: 'warning',
      crud: 'primary',
      integration: 'info',
      e2e: 'primary',
    };
    return colors[type] || 'default';
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      happy_path: 'Happy Path',
      negative: 'Negative',
      boundary: 'Boundary',
      security: 'Security',
      performance: 'Performance',
      validation: 'Validation',
      crud: 'CRUD',
      integration: 'Integration',
      e2e: 'E2E',
      all: 'All Tests',
    };
    return labels[type] || type;
  };

  const getEndpointDomId = (endpointKey: string) =>
    `endpoint-${endpointKey.replace(/[^a-zA-Z0-9]/g, '-')}`;

  // Normalize tests and filtered list (must be before early returns to satisfy hook order)
  const allTests = useMemo(
    () => testSuite?.all_tests || testSuite?.all_test_cases || [],
    [testSuite]
  );
  const filteredTests = useMemo(() => {
    if (!searchQuery.trim()) return allTests;
    const query = searchQuery.toLowerCase();
    return allTests.filter((testCase: TestCase) => {
      const endpointMatch = testCase.endpoint?.toLowerCase().includes(query);
      const methodMatch = testCase.method?.toLowerCase().includes(query);
      const nameMatch = testCase.name?.toLowerCase().includes(query);
      const typeMatch = testCase.type?.toLowerCase().includes(query);
      const descriptionMatch = testCase.description?.toLowerCase().includes(query);
      return endpointMatch || methodMatch || nameMatch || typeMatch || descriptionMatch;
    });
  }, [allTests, searchQuery]);

  const handleJumpToEndpoint = (endpointKey: string) => {
    setViewMode('grouped');
    setExpandedEndpoints((prev) => {
      const next = new Set(prev);
      next.add(endpointKey);
      return next;
    });
    // Scroll to accordion after state update
    setTimeout(() => {
      const el = document.getElementById(getEndpointDomId(endpointKey));
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 50);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!testSuite) {
    return <Alert severity="error">Test suite not found</Alert>;
  }

  const selectedCount = allTests.filter((t: TestCase) => selectedTests.has(t.index)).length;
  
  // Get all endpoint keys sorted
  const endpointKeys = Object.keys(testCasesByEndpoint).sort();

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={() => navigate('/')}
          sx={{ display: 'flex', alignItems: 'center', textDecoration: 'none', color: 'inherit' }}
        >
          <Home sx={{ mr: 0.5 }} fontSize="inherit" />
          Dashboard
        </Link>
        {projectInfo && (
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate(`/projects/${projectInfo.id}`)}
            sx={{ display: 'flex', alignItems: 'center', textDecoration: 'none', color: 'inherit' }}
          >
            <Folder sx={{ mr: 0.5 }} fontSize="inherit" />
            {projectInfo.name}
          </Link>
        )}
        <Typography color="text.primary" sx={{ display: 'flex', alignItems: 'center' }}>
          {testSuite?.name || 'Test Suite'}
        </Typography>
      </Breadcrumbs>

        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexWrap="wrap" gap={2}>
        <Typography variant="h4" component="h1">
          {testSuite?.name || 'Test Suite'}
        </Typography>
        <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
          <Chip
            label={`${selectedTests.size} selected`}
            color="primary"
            variant="outlined"
          />
          <Button
            variant="outlined"
            onClick={() => navigate(`/reports/test-suite/${testSuiteId}`)}
          >
            View Reports
          </Button>
          <Button
            variant="contained"
            startIcon={<PlayArrow />}
            onClick={handleExecuteSelected}
            disabled={selectedTests.size === 0 || executing}
          >
            Execute Selected ({selectedTests.size})
          </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={handleDeleteAll}
              disabled={deletingAll || (testSuite?.test_count ?? 0) === 0}
            >
              {deletingAll ? 'Deleting…' : 'Delete All'}
            </Button>
        </Box>
      </Box>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Suite Overview
          </Typography>
          <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
            <Chip label={`Total Tests: ${testSuite.test_count}`} />
            <Chip label={`Endpoints: ${endpointKeys.length}`} color="primary" />
            <Chip label={`Selected: ${selectedCount}`} color={selectedCount > 0 ? 'success' : 'default'} />
          </Box>
        </CardContent>
      </Card>

      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={2}>
        <TextField
          placeholder="Search tests by endpoint, method, name, type, or description..."
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
          sx={{ flex: 1, minWidth: 280, maxWidth: 500 }}
        />
        <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            size="small"
            onChange={(_, value) => value && setViewMode(value)}
          >
            <ToggleButton value="grouped">
              <ViewModule fontSize="small" sx={{ mr: 0.5 }} />
              Grouped
            </ToggleButton>
            <ToggleButton value="list">
              <ViewList fontSize="small" sx={{ mr: 0.5 }} />
              List
            </ToggleButton>
          </ToggleButtonGroup>
          <Tooltip title="Select All Tests">
            <IconButton size="small" onClick={handleSelectAll}>
              <SelectAll />
            </IconButton>
          </Tooltip>
          <Tooltip title="Deselect All Tests">
            <IconButton size="small" onClick={handleDeselectAll}>
              <Deselect />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" color="textSecondary" sx={{ alignSelf: 'center', ml: 1 }}>
            {selectedCount} of {testSuite.test_count} selected
          </Typography>
        </Box>
      </Box>

      <Box>
        {viewMode === 'list' ? (
          <TableContainer component={Paper} sx={{ maxHeight: '70vh', overflow: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" width={50}></TableCell>
                  <TableCell>Method</TableCell>
                  <TableCell>Endpoint</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell>Expected Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredTests.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography color="textSecondary">
                        {searchQuery ? 'No tests found matching your search' : 'No test cases found'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTests.map((testCase) => (
                    <TableRow key={testCase.index} hover>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedTests.has(testCase.index)}
                          onChange={() => handleSelectTest(testCase.index)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={testCase.method}
                          color={
                            testCase.method === 'GET' ? 'success' :
                            testCase.method === 'POST' ? 'primary' :
                            testCase.method === 'PUT' ? 'info' :
                            testCase.method === 'DELETE' ? 'error' : 'default'
                          }
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          fontFamily="monospace"
                          fontWeight="medium"
                          sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                          onClick={() => handleJumpToEndpoint(`${testCase.method}:${testCase.endpoint}`)}
                        >
                          {testCase.endpoint}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getTypeLabel(testCase.type)}
                          color={getTypeColor(testCase.type)}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {testCase.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="textSecondary" noWrap>
                          {testCase.description || 'No description'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={testCase.expected_status?.join(', ') || '200'}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" gap={0.5}>
                          <Tooltip title="View Details">
                            <IconButton
                              size="small"
                              onClick={() => {
                                const assertionInfo = testCase.assertions && testCase.assertions.length > 0
                                  ? `\n\nAssertions (${testCase.assertions.length}):\n${testCase.assertions.map((a: Assertion, idx: number) => 
                                      `${idx + 1}. ${a.type?.replace('_', ' ')} - ${a.condition}${a.field ? ` (field: ${a.field})` : ''}${a.description ? ` - ${a.description}` : ''}`
                                    ).join('\n')}`
                                  : '\n\nNo assertions defined';
                                alert(`Test: ${testCase.name}\nEndpoint: ${testCase.method} ${testCase.endpoint}\nType: ${getTypeLabel(testCase.type)}\nPayload: ${JSON.stringify(testCase.payload, null, 2)}${assertionInfo}`);
                              }}
                            >
                              <Visibility fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Edit Request">
                            <IconButton
                              size="small"
                              onClick={() => handleEditTest(testCase)}
                              color="primary"
                            >
                              <Edit fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Run Test">
                            <IconButton
                              size="small"
                              onClick={() => handleRunSingleTest(testCase)}
                              disabled={runningTest === testCase.index}
                              color="success"
                            >
                              {runningTest === testCase.index ? (
                                <CircularProgress size={16} />
                              ) : (
                                <PlayArrow fontSize="small" />
                              )}
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        ) : endpointKeys.length === 0 ? (
          <Alert severity="info">No test cases found</Alert>
        ) : (
          endpointKeys.map((endpointKey) => {
            const [method, path] = endpointKey.split(':');
            const endpointTests = testCasesByEndpoint[endpointKey] || {};
            const typeKeys = Object.keys(endpointTests).sort();
            const allTestsInEndpoint: TestCase[] = [];
            Object.values(endpointTests).forEach(typeTests => {
              allTestsInEndpoint.push(...typeTests);
            });
            
            const endpointSelectedCount = allTestsInEndpoint.filter(t => selectedTests.has(t.index)).length;
            const isAllSelected = allTestsInEndpoint.length > 0 && 
              allTestsInEndpoint.every(t => selectedTests.has(t.index));
            const isExpanded = expandedEndpoints.has(endpointKey);

            return (
              <Accordion
                key={endpointKey}
                expanded={isExpanded}
                onChange={() => handleToggleEndpoint(endpointKey)}
                sx={{ mb: 2 }}
                id={getEndpointDomId(endpointKey)}
              >
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Box display="flex" alignItems="center" gap={2} width="100%">
                    <Checkbox
                      checked={isAllSelected}
                      indeterminate={endpointSelectedCount > 0 && endpointSelectedCount < allTestsInEndpoint.length}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectEndpoint(endpointKey);
                      }}
                    />
                    <Chip
                      label={method}
                      color={
                        method === 'GET' ? 'success' :
                        method === 'POST' ? 'primary' :
                        method === 'PUT' ? 'info' :
                        method === 'DELETE' ? 'error' : 'default'
                      }
                      size="small"
                    />
                    <Typography variant="body1" fontFamily="monospace" fontWeight="medium" sx={{ flex: 1 }}>
                      {path}
                    </Typography>
                    <Chip
                      label={`${allTestsInEndpoint.length} tests`}
                      size="small"
                      variant="outlined"
                    />
                    {endpointSelectedCount > 0 && (
                      <Chip
                        label={`${endpointSelectedCount} selected`}
                        color="success"
                        size="small"
                      />
                    )}
                    <Tooltip title="Delete all tests for this endpoint">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteEndpoint(endpointKey);
                        }}
                        disabled={deletingEndpoint === endpointKey}
                      >
                        {deletingEndpoint === endpointKey ? (
                          <CircularProgress size={20} />
                        ) : (
                          <Delete />
                        )}
                      </IconButton>
                    </Tooltip>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Box>
                    {typeKeys.map((type) => {
                      const typeTests = endpointTests[type] || [];
                      const typeSelectedCount = typeTests.filter(t => selectedTests.has(t.index)).length;
                      const isTypeAllSelected = typeTests.length > 0 && 
                        typeTests.every(t => selectedTests.has(t.index));

                      return (
                        <Box key={type} sx={{ mb: 3 }}>
                          <Box display="flex" alignItems="center" gap={2} mb={1}>
                            <Checkbox
                              checked={isTypeAllSelected}
                              indeterminate={typeSelectedCount > 0 && typeSelectedCount < typeTests.length}
                              onChange={() => handleSelectType(endpointKey, type)}
                              size="small"
                            />
                            <Chip
                              label={getTypeLabel(type)}
                              color={getTypeColor(type)}
                              size="small"
                            />
                            <Typography variant="body2" color="textSecondary">
                              {typeTests.length} test{typeTests.length !== 1 ? 's' : ''}
                            </Typography>
                            {typeSelectedCount > 0 && (
                              <Chip
                                label={`${typeSelectedCount} selected`}
                                color="success"
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                          <TableContainer
                            component={Paper}
                            variant="outlined"
                            sx={{ ml: 4, maxHeight: '60vh', overflow: 'auto' }}
                          >
                            <Table size="small" stickyHeader>
                              <TableHead>
                                <TableRow>
                                  <TableCell padding="checkbox" width={50}></TableCell>
                                  <TableCell>Test Name</TableCell>
                                  <TableCell>Description</TableCell>
                                  <TableCell>Expected Status</TableCell>
                                  <TableCell>Actions</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {typeTests.map((testCase) => (
                                  <TableRow key={testCase.index} hover>
                                    <TableCell padding="checkbox">
                                      <Checkbox
                                        checked={selectedTests.has(testCase.index)}
                                        onChange={() => handleSelectTest(testCase.index)}
                                        size="small"
                                      />
                                    </TableCell>
                                    <TableCell>
                                      <Box display="flex" alignItems="center" gap={1}>
                                        <Typography variant="body2" fontWeight="medium">
                                          {testCase.name}
                                        </Typography>
                                        {testCase.assertions && testCase.assertions.length > 0 && (
                                          <Chip
                                            label={`${testCase.assertions.length} assertion${testCase.assertions.length > 1 ? 's' : ''}`}
                                            size="small"
                                            color="success"
                                            variant="outlined"
                                            sx={{ fontSize: '0.7rem', height: '20px' }}
                                          />
                                        )}
                                      </Box>
                                    </TableCell>
                                    <TableCell>
                                      <Box>
                                        <Typography variant="body2" color="textSecondary">
                                          {testCase.description || 'No description'}
                                        </Typography>
                                        {testCase.assertions && testCase.assertions.length > 0 && (
                                          <Box sx={{ mt: 1 }}>
                                            <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 0.5 }}>
                                              <strong>Assertions:</strong>
                                            </Typography>
                                            <Box display="flex" flexWrap="wrap" gap={0.5}>
                                              {testCase.assertions.slice(0, 3).map((assertion: Assertion, idx: number) => (
                                                <Chip
                                                  key={idx}
                                                  label={`${assertion.type?.replace('_', ' ') || 'assertion'}: ${assertion.condition || 'check'}`}
                                                  size="small"
                                                  color="info"
                                                  variant="outlined"
                                                  sx={{ fontSize: '0.65rem', height: '18px' }}
                                                />
                                              ))}
                                              {testCase.assertions.length > 3 && (
                                                <Chip
                                                  label={`+${testCase.assertions.length - 3} more`}
                                                  size="small"
                                                  color="info"
                                                  variant="outlined"
                                                  sx={{ fontSize: '0.65rem', height: '18px' }}
                                                />
                                              )}
                                            </Box>
                                          </Box>
                                        )}
                                      </Box>
                                    </TableCell>
                                    <TableCell>
                                      <Chip
                                        label={testCase.expected_status?.join(', ') || '200'}
                                        size="small"
                                        variant="outlined"
                                      />
                                    </TableCell>
                                    <TableCell>
                                      <Box display="flex" gap={0.5}>
                                        <Tooltip title="View Details">
                                          <IconButton
                                            size="small"
                                            onClick={() => {
                                              const assertionInfo = testCase.assertions && testCase.assertions.length > 0
                                                ? `\n\nAssertions (${testCase.assertions.length}):\n${testCase.assertions.map((a: Assertion, idx: number) => 
                                                    `${idx + 1}. ${a.type?.replace('_', ' ')} - ${a.condition}${a.field ? ` (field: ${a.field})` : ''}${a.description ? ` - ${a.description}` : ''}`
                                                  ).join('\n')}`
                                                : '\n\nNo assertions defined';
                                              alert(`Test: ${testCase.name}\nEndpoint: ${testCase.method} ${testCase.endpoint}\nType: ${getTypeLabel(testCase.type)}\nPayload: ${JSON.stringify(testCase.payload, null, 2)}${assertionInfo}`);
                                            }}
                                          >
                                            <Visibility fontSize="small" />
                                          </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Edit Request">
                                          <IconButton
                                            size="small"
                                            onClick={() => handleEditTest(testCase)}
                                            color="primary"
                                          >
                                            <Edit fontSize="small" />
                                          </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Run Test">
                                          <IconButton
                                            size="small"
                                            onClick={() => handleRunSingleTest(testCase)}
                                            disabled={runningTest === testCase.index}
                                            color="success"
                                          >
                                            {runningTest === testCase.index ? (
                                              <CircularProgress size={16} />
                                            ) : (
                                              <PlayArrow fontSize="small" />
                                            )}
                                          </IconButton>
                                        </Tooltip>
                                      </Box>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                          {typeKeys.indexOf(type) < typeKeys.length - 1 && (
                            <Divider sx={{ mt: 2 }} />
                          )}
                        </Box>
                      );
                    })}
                  </Box>
                </AccordionDetails>
              </Accordion>
            );
          })
        )}
      </Box>

      {/* Edit Test Case Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={handleCloseEditDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Edit Test Case Request</DialogTitle>
        <DialogContent>
          {editingTestCase && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Method:</strong> {editingTestCase.method} | <strong>Endpoint:</strong> {editingTestCase.endpoint}
              </Typography>
              <TextField
                label={editingTestCase.payload?.__is_form_data__ || editingTestCase.payload?.__is_multipart__ 
                  ? "Form Data / Query Parameters (JSON)" 
                  : "Request Payload (JSON)"}
                fullWidth
                multiline
                rows={10}
                value={editedPayload}
                onChange={(e) => setEditedPayload(e.target.value)}
                sx={{ mt: 2 }}
                variant="outlined"
                helperText={
                  editingTestCase.payload?.__is_multipart__ 
                    ? "Edit form data for multipart/form-data. Use '__FILE__' for file parameters."
                    : editingTestCase.payload?.__is_form_data__
                    ? "Edit form data for application/x-www-form-urlencoded"
                    : "Edit the JSON payload for this request. For GET/DELETE, these are query parameters."
                }
              />
              <TextField
                label="Request Headers (JSON)"
                fullWidth
                multiline
                rows={4}
                value={editedHeaders}
                onChange={(e) => setEditedHeaders(e.target.value)}
                sx={{ mt: 2 }}
                variant="outlined"
                helperText="Edit the JSON headers for this request"
              />
              
              <Box sx={{ mt: 3 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Assertions</Typography>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleAddAssertion}
                    startIcon={<Edit />}
                  >
                    Add Assertion
                  </Button>
                </Box>
                
                {editedAssertions.length === 0 ? (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    {editingTestCase?.assertions && editingTestCase.assertions.length > 0 
                      ? `${editingTestCase.assertions.length} assertion(s) were automatically generated from OpenAPI response schemas based on status codes (200, 400, etc.) and their descriptions. These will be used during test execution.`
                      : 'No assertions defined. Click "Add Assertion" to add validation rules. Note: Assertions are automatically generated from OpenAPI response schemas (status codes, descriptions, array/object structures) when you generate new tests. Regenerate tests to see auto-generated assertions.'}
                  </Alert>
                ) : (
                  <Box>
                    {editedAssertions.map((assertion, index) => (
                      <Card key={index} sx={{ mb: 1 }}>
                        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                          <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                            <Box flex={1}>
                              <Box display="flex" gap={1} alignItems="center" mb={0.5}>
                                <Chip
                                  label={assertion.type.replace('_', ' ')}
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                />
                                <Chip
                                  label={assertion.condition}
                                  size="small"
                                  color="secondary"
                                  variant="outlined"
                                />
                                {assertion.field && (
                                  <Chip
                                    label={`Field: ${assertion.field}`}
                                    size="small"
                                    variant="outlined"
                                  />
                                )}
                              </Box>
                              <Typography variant="body2" color="textSecondary">
                                <strong>Expected:</strong> {JSON.stringify(assertion.expected_value)}
                              </Typography>
                              {assertion.description && (
                                <Typography variant="body2" color="textSecondary" sx={{ mt: 0.5 }}>
                                  {assertion.description}
                                </Typography>
                              )}
                            </Box>
                            <Box display="flex" gap={0.5}>
                              <IconButton
                                size="small"
                                onClick={() => handleEditAssertion(assertion, index)}
                                color="primary"
                              >
                                <Edit fontSize="small" />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={() => handleDeleteAssertion(index)}
                                color="error"
                              >
                                <Cancel fontSize="small" />
                              </IconButton>
                            </Box>
                          </Box>
                        </CardContent>
                      </Card>
                    ))}
                  </Box>
                )}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseEditDialog}>Cancel</Button>
          <Button
            onClick={() => editingTestCase && handleRunSingleTest(editingTestCase, true)}
            variant="contained"
            color="primary"
            disabled={runningTest === editingTestCase?.index}
            startIcon={runningTest === editingTestCase?.index ? <CircularProgress size={16} /> : <PlayArrow />}
          >
            Run with Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* Test Result Dialog */}
      <Dialog
        open={resultDialogOpen}
        onClose={() => setResultDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            {testResult?.result?.status === 'passed' ? (
              <CheckCircle color="success" />
            ) : testResult?.result?.status === 'failed' ? (
              <Cancel color="error" />
            ) : null}
            Test Execution Result
          </Box>
        </DialogTitle>
        <DialogContent>
          {testResult && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="h6" gutterBottom>
                {testResult.result?.test_name || 'Test Result'}
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Chip
                  label={`Status: ${testResult.result?.status || 'unknown'}`}
                  color={
                    testResult.result?.status === 'passed' ? 'success' :
                    testResult.result?.status === 'failed' ? 'error' : 'default'
                  }
                  sx={{ mr: 1 }}
                />
                <Chip
                  label={`Expected: ${testResult.result?.expected_status?.join(', ') || 'N/A'}`}
                  variant="outlined"
                  sx={{ mr: 1 }}
                />
                <Chip
                  label={`Actual: ${testResult.result?.actual_status || 'N/A'}`}
                  variant="outlined"
                />
              </Box>
              
              {testResult.result?.error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {testResult.result.error}
                </Alert>
              )}
              
              {testResult.result?.note && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {testResult.result.note}
                </Alert>
              )}

              <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                Response Body:
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.100', maxHeight: 300, overflow: 'auto' }}>
                <Typography
                  component="pre"
                  sx={{
                    fontSize: '0.75rem',
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    margin: 0,
                  }}
                >
                  {testResult.result?.response_body || 'No response body'}
                </Typography>
              </Paper>

              {testResult.result?.response_headers && (
                <>
                  <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                    Response Headers:
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.100', maxHeight: 200, overflow: 'auto' }}>
                    <Typography
                      component="pre"
                      sx={{
                        fontSize: '0.75rem',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        margin: 0,
                      }}
                    >
                      {JSON.stringify(testResult.result.response_headers, null, 2)}
                    </Typography>
                  </Paper>
                </>
              )}

              {testResult.result?.assertion_results && testResult.result.assertion_results.length > 0 && (
                <>
                  <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                    Assertion Results:
                  </Typography>
                  <Box>
                    {testResult.result.assertion_results.map((assertion: any, index: number) => (
                      <Alert
                        key={index}
                        severity={assertion.passed ? 'success' : 'error'}
                        sx={{ mb: 1 }}
                      >
                        <Typography variant="body2">
                          <strong>{assertion.type?.replace('_', ' ') || 'Assertion'}:</strong> {assertion.message || 'No message'}
                        </Typography>
                        {assertion.actual_value !== undefined && (
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            Actual: {JSON.stringify(assertion.actual_value)}
                          </Typography>
                        )}
                      </Alert>
                    ))}
                  </Box>
                </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResultDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Assertion Editor Dialog */}
      <Dialog
        open={assertionDialogOpen}
        onClose={() => {
          setAssertionDialogOpen(false);
          setEditingAssertion(null);
          setAssertionIndex(-1);
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {assertionIndex >= 0 ? 'Edit Assertion' : 'Add Assertion'}
        </DialogTitle>
        <DialogContent>
          {editingAssertion && (
            <Box sx={{ mt: 2 }}>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Assertion Type</InputLabel>
                <Select
                  value={editingAssertion.type}
                  onChange={(e) => setEditingAssertion({
                    ...editingAssertion,
                    type: e.target.value as Assertion['type']
                  })}
                  label="Assertion Type"
                >
                  <MenuItem value="status_code">Status Code</MenuItem>
                  <MenuItem value="response_body">Response Body</MenuItem>
                  <MenuItem value="response_header">Response Header</MenuItem>
                  <MenuItem value="response_time">Response Time</MenuItem>
                  <MenuItem value="custom">Custom</MenuItem>
                </Select>
              </FormControl>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Condition</InputLabel>
                <Select
                  value={editingAssertion.condition}
                  onChange={(e) => setEditingAssertion({
                    ...editingAssertion,
                    condition: e.target.value
                  })}
                  label="Condition"
                >
                  <MenuItem value="equals">Equals</MenuItem>
                  <MenuItem value="not_equals">Not Equals</MenuItem>
                  <MenuItem value="contains">Contains</MenuItem>
                  <MenuItem value="not_contains">Not Contains</MenuItem>
                  <MenuItem value="greater_than">Greater Than</MenuItem>
                  <MenuItem value="less_than">Less Than</MenuItem>
                  <MenuItem value="matches">Matches (Regex)</MenuItem>
                  <MenuItem value="exists">Exists</MenuItem>
                  <MenuItem value="not_exists">Not Exists</MenuItem>
                </Select>
              </FormControl>

              {(editingAssertion.type === 'response_body' || editingAssertion.type === 'response_header') && (
                <TextField
                  label="Field/Path"
                  fullWidth
                  value={editingAssertion.field || ''}
                  onChange={(e) => setEditingAssertion({
                    ...editingAssertion,
                    field: e.target.value
                  })}
                  sx={{ mb: 2 }}
                  helperText="JSON path (e.g., 'data.id' or '$.user.name')"
                />
              )}

              <TextField
                label="Expected Value"
                fullWidth
                value={editingAssertion.expected_value !== undefined ? JSON.stringify(editingAssertion.expected_value) : ''}
                onChange={(e) => {
                  try {
                    const value = e.target.value ? JSON.parse(e.target.value) : undefined;
                    setEditingAssertion({
                      ...editingAssertion,
                      expected_value: value
                    });
                  } catch {
                    // If not valid JSON, store as string
                    setEditingAssertion({
                      ...editingAssertion,
                      expected_value: e.target.value
                    });
                  }
                }}
                sx={{ mb: 2 }}
                helperText='Enter value as JSON (e.g., 200, "success", true)'
              />

              <TextField
                label="Description (Optional)"
                fullWidth
                multiline
                rows={2}
                value={editingAssertion.description || ''}
                onChange={(e) => setEditingAssertion({
                  ...editingAssertion,
                  description: e.target.value
                })}
                helperText="Describe what this assertion validates"
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setAssertionDialogOpen(false);
            setEditingAssertion(null);
            setAssertionIndex(-1);
          }}>
            Cancel
          </Button>
          <Button onClick={handleSaveAssertion} variant="contained" color="primary">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TestSuite;

