import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
} from '@mui/material';
import { Download, Refresh } from '@mui/icons-material';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import api from '../services/api';

interface ReportData {
  execution_id?: string;
  test_suite_id?: string;
  test_suite_name?: string;
  project_id?: string;
  project_name?: string;
  status?: string;
  started_at?: string;
  completed_at?: string;
  summary: {
    total_executions: number;
    total_tests: number;
    total_passed: number;
    total_failed: number;
    total_errors: number;
    pass_rate: number;
    period_days: number;
  };
  test_type_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  daily_trends?: Array<{
    date: string;
    executions: number;
    tests: number;
    passed: number;
    failed: number;
    errors: number;
  }>;
  security_findings: Array<{
    test_name: string;
    endpoint: string;
    method: string;
    error: string;
    execution_id: string;
    date: string;
  }>;
  endpoint_performance: Array<{
    endpoint: string;
    method: string;
    total: number;
    passed: number;
    failed: number;
    errors: number;
  }>;
  time_range: {
    start: string;
    end: string;
  };
  results?: Array<any>;
}

const COLORS = ['#4caf50', '#f44336', '#ff9800', '#2196f3', '#9c27b0', '#00bcd4'];

type ReportMode = 'period' | 'last-run';

const Reports: React.FC = () => {
  const { projectId, testSuiteId } = useParams<{ projectId?: string; testSuiteId?: string }>();
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [reportMode, setReportMode] = useState<ReportMode>('period');
  const [downloading, setDownloading] = useState(false);
  const [projectsData, setProjectsData] = useState<any[]>([]);
  const [testSuiteName, setTestSuiteName] = useState<string>('');
  const [projectName, setProjectName] = useState<string>('');

  useEffect(() => {
    if (!projectId && !testSuiteId) {
      // Global report - fetch projects with test suites
      fetchProjectsData();
    }
    fetchReportData();
  }, [projectId, testSuiteId, days, reportMode]);

  const fetchProjectsData = async () => {
    try {
      const response = await api.get('/reports/projects');
      setProjectsData(response.data);
    } catch (error: any) {
      console.error('Failed to fetch projects data:', error);
    }
  };

  const fetchReportData = async () => {
    try {
      setLoading(true);
      let url: string;
      if (reportMode === 'last-run') {
        if (testSuiteId) {
          url = `/reports/last-run?test_suite_id=${testSuiteId}`;
        } else {
          url = projectId 
            ? `/reports/last-run?project_id=${projectId}`
            : `/reports/last-run`;
        }
      } else {
        if (testSuiteId) {
          url = `/reports/test-suite/${testSuiteId}?days=${days}`;
        } else if (projectId) {
          url = `/reports/project/${projectId}?days=${days}`;
        } else {
          url = `/reports/?days=${days}`;
        }
      }
      const response = await api.get(url);
      const data = response.data;
      setReportData(data);
      
      // Store names for use in error messages and titles
      if (data.test_suite_name) {
        setTestSuiteName(data.test_suite_name);
      }
      if (data.project_name) {
        setProjectName(data.project_name);
      }
    } catch (error: any) {
      console.error('Failed to fetch report data:', error);
      if (error.response?.status === 404 && reportMode === 'last-run') {
        // No last run found, show message
        setReportData(null);
        // Try to fetch test suite/project names for context
        if (testSuiteId) {
          try {
            const suiteResponse = await api.get(`/generate/${testSuiteId}/cases`);
            if (suiteResponse.data.name) {
              setTestSuiteName(suiteResponse.data.name);
            }
          } catch (e) {
            // Ignore
          }
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      setDownloading(true);
      const reportElement = document.getElementById('report-content');
      if (!reportElement) {
        alert('Report content not found');
        return;
      }

      // Create canvas from the report content
      const canvas = await html2canvas(reportElement, {
        scale: 2,
        useCORS: true,
        logging: false,
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = canvas.width;
      const imgHeight = canvas.height;
      const ratio = Math.min(pdfWidth / imgWidth, pdfHeight / imgHeight);
      const imgScaledWidth = imgWidth * ratio;
      const imgScaledHeight = imgHeight * ratio;
      
      // Calculate how many pages needed
      const pageCount = Math.ceil(imgScaledHeight / pdfHeight);
      
      for (let i = 0; i < pageCount; i++) {
        if (i > 0) {
          pdf.addPage();
        }
        pdf.addImage(
          imgData,
          'PNG',
          0,
          -(i * pdfHeight),
          imgScaledWidth,
          imgScaledHeight
        );
      }

      // Generate filename
      const timestamp = new Date().toISOString().split('T')[0];
      const filename = reportMode === 'last-run' 
        ? `test-report-last-run-${timestamp}.pdf`
        : `test-report-${days}days-${timestamp}.pdf`;
      
      pdf.save(filename);
    } catch (error) {
      console.error('Failed to generate PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  // Show projects with test suites for global reports when no project/testSuite selected
  if (!projectId && !testSuiteId && !loading && projectsData.length > 0 && !reportData) {
    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h4" component="h1">
            Global Test Reports
          </Typography>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => {
              fetchProjectsData();
              fetchReportData();
            }}
          >
            Refresh
          </Button>
        </Box>
        
        <Grid container spacing={3}>
          {projectsData.map((project) => (
            <Grid item xs={12} md={6} key={project.id}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {project.name}
                  </Typography>
                  {project.description && (
                    <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                      {project.description}
                    </Typography>
                  )}
                  <Typography variant="subtitle2" gutterBottom>
                    Test Suites ({project.test_suites.length})
                  </Typography>
                  {project.test_suites.length === 0 ? (
                    <Typography variant="body2" color="textSecondary">
                      No test suites found
                    </Typography>
                  ) : (
                    <Box>
                      {project.test_suites.map((suite: any) => (
                        <Box key={suite.id} sx={{ mb: 1, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
                          <Box display="flex" justifyContent="space-between" alignItems="center">
                            <Box>
                              <Typography variant="body2" fontWeight="medium">
                                {suite.name}
                              </Typography>
                              <Typography variant="caption" color="textSecondary">
                                {suite.test_count} tests • {suite.execution_count} executions
                              </Typography>
                            </Box>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => window.location.href = `/reports/test-suite/${suite.id}`}
                            >
                              View Report
                            </Button>
                          </Box>
                          {suite.latest_execution && (
                            <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5, display: 'block' }}>
                              Last run: {suite.latest_execution.completed_at 
                                ? new Date(suite.latest_execution.completed_at).toLocaleString()
                                : 'In progress'}
                            </Typography>
                          )}
                        </Box>
                      ))}
                    </Box>
                  )}
                  <Button
                    variant="contained"
                    fullWidth
                    sx={{ mt: 2 }}
                    onClick={() => window.location.href = `/reports/project/${project.id}`}
                  >
                    View Project Report
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (!reportData && !loading) {
    if (reportMode === 'last-run') {
      return (
        <Box>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
            <Typography variant="h4" component="h1">
              {testSuiteId
                ? `Test Suite Report${testSuiteName ? `: ${testSuiteName}` : ''}`
                : projectId 
                  ? `Project Report${projectName ? `: ${projectName}` : ''}` 
                  : 'Last Run Report'}
            </Typography>
            <Button
              variant="outlined"
              onClick={() => setReportMode('period')}
            >
              View Period Report
            </Button>
          </Box>
          <Alert severity="info" sx={{ mb: 3 }}>
            <Typography variant="body1" gutterBottom>
              <strong>No test executions found.</strong>
            </Typography>
            <Typography variant="body2">
              To generate reports, you need to execute tests first. Here's how:
            </Typography>
            <Box component="ol" sx={{ mt: 1, mb: 0, pl: 2 }}>
              <li>Navigate to your project's Test Suite page</li>
              <li>Select the test cases you want to run</li>
              <li>Click "Execute Selected" to run the tests</li>
              <li>Once tests are executed, reports will be available here</li>
            </Box>
          </Alert>
          {testSuiteId && (
            <Button
              variant="contained"
              onClick={() => window.location.href = `/test-suites/${testSuiteId}`}
              sx={{ mt: 2 }}
            >
              Go to Test Suite
            </Button>
          )}
          {projectId && !testSuiteId && (
            <Button
              variant="contained"
              onClick={() => window.location.href = `/projects/${projectId}`}
              sx={{ mt: 2 }}
            >
              Go to Project
            </Button>
          )}
        </Box>
      );
    }
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load report data
        </Alert>
        <Button
          variant="outlined"
          onClick={fetchReportData}
        >
          Retry
        </Button>
      </Box>
    );
  }

  if (!reportData) {
    return null;
  }

  const { summary, test_type_breakdown, status_breakdown, daily_trends, security_findings, endpoint_performance } = reportData;
  
  // Check if there are no executions
  const hasNoExecutions = summary.total_executions === 0 && summary.total_tests === 0;

  // Show message if no executions found (for period reports)
  if (hasNoExecutions && reportMode === 'period') {
    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h4" component="h1">
            {testSuiteId
              ? `Test Suite Report${testSuiteName ? `: ${testSuiteName}` : ''}`
              : projectId 
                ? `Project Report${projectName ? `: ${projectName}` : ''}` 
                : 'Overall Test Reports'}
          </Typography>
          <Box display="flex" gap={2}>
            <FormControl variant="outlined" size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Report Type</InputLabel>
              <Select
                value={reportMode}
                onChange={(e) => {
                  setReportMode(e.target.value as ReportMode);
                  if (e.target.value === 'period') {
                    setDays(30);
                  }
                }}
                label="Report Type"
              >
                <MenuItem value="period">Time Period</MenuItem>
                <MenuItem value="last-run">Last Run</MenuItem>
              </Select>
            </FormControl>
            {reportMode === 'period' && (
              <FormControl variant="outlined" size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Time Period</InputLabel>
                <Select
                  value={days}
                  onChange={(e) => setDays(e.target.value as number)}
                  label="Time Period"
                >
                  <MenuItem value={7}>Last 7 Days</MenuItem>
                  <MenuItem value={30}>Last 30 Days</MenuItem>
                  <MenuItem value={90}>Last 90 Days</MenuItem>
                  <MenuItem value={365}>Last 365 Days</MenuItem>
                </Select>
              </FormControl>
            )}
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={fetchReportData}
              disabled={loading}
            >
              Refresh
            </Button>
          </Box>
        </Box>
        
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body1" gutterBottom>
            <strong>No test executions found for the selected period.</strong>
          </Typography>
          <Typography variant="body2">
            To generate reports, you need to execute tests first. Here's how:
          </Typography>
          <Box component="ol" sx={{ mt: 1, mb: 0, pl: 2 }}>
            <li>Navigate to your project's Test Suite page</li>
            <li>Select the test cases you want to run</li>
            <li>Click "Execute Selected" to run the tests</li>
            <li>Once tests are executed, reports will be available here</li>
          </Box>
        </Alert>
        
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Summary
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="body2" color="textSecondary">Total Executions</Typography>
                <Typography variant="h5">{summary.total_executions}</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="body2" color="textSecondary">Total Tests</Typography>
                <Typography variant="h5">{summary.total_tests}</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="body2" color="textSecondary">Pass Rate</Typography>
                <Typography variant="h5">{summary.pass_rate.toFixed(1)}%</Typography>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="body2" color="textSecondary">Period</Typography>
                <Typography variant="h5">Last {summary.period_days} Days</Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
        
        {testSuiteId && (
          <Button
            variant="contained"
            onClick={() => window.location.href = `/test-suites/${testSuiteId}`}
            sx={{ mt: 2 }}
          >
            Go to Test Suite
          </Button>
        )}
        {projectId && !testSuiteId && (
          <Button
            variant="contained"
            onClick={() => window.location.href = `/projects/${projectId}`}
            sx={{ mt: 2 }}
          >
            Go to Project
          </Button>
        )}
      </Box>
    );
  }

  // Handle last run report (may not have daily_trends)
  const hasDailyTrends = daily_trends && daily_trends.length > 0;

  // Prepare chart data
  const statusChartData = [
    { name: 'Passed', value: summary.total_passed, color: '#4caf50' },
    { name: 'Failed', value: summary.total_failed, color: '#f44336' },
    { name: 'Errors', value: summary.total_errors, color: '#ff9800' },
  ].filter(item => item.value > 0);

  const testTypeChartData = Object.entries(test_type_breakdown).map(([name, value]) => ({
    name: name.replace('_', ' ').toUpperCase(),
    value,
  }));

  const dailyChartData = hasDailyTrends ? (daily_trends || []).map(day => ({
    date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    Passed: day.passed,
    Failed: day.failed,
    Errors: day.errors,
  })) : [];

  const endpointChartData = endpoint_performance
    .sort((a, b) => b.total - a.total)
    .slice(0, 10)
    .map(endpoint => ({
      name: `${endpoint.method} ${endpoint.endpoint.substring(0, 30)}${endpoint.endpoint.length > 30 ? '...' : ''}`,
      Passed: endpoint.passed,
      Failed: endpoint.failed,
      Errors: endpoint.errors,
    }));

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          {reportMode === 'last-run' 
            ? `Last Run Report${reportData && 'execution_id' in reportData && reportData.execution_id ? ` - ${reportData.execution_id.substring(0, 8)}` : ''}`
            : testSuiteId
              ? `Test Suite Report${reportData && 'test_suite_name' in reportData ? `: ${reportData.test_suite_name}` : ''}`
              : projectId 
                ? `Project Report${reportData && 'project_name' in reportData ? `: ${reportData.project_name}` : ''}` 
                : 'Overall Test Reports'}
        </Typography>
        <Box display="flex" gap={2}>
          <FormControl variant="outlined" size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Report Type</InputLabel>
            <Select
              value={reportMode}
              onChange={(e) => {
                setReportMode(e.target.value as ReportMode);
                if (e.target.value === 'period') {
                  setDays(30);
                }
              }}
              label="Report Type"
            >
              <MenuItem value="period">Time Period</MenuItem>
              <MenuItem value="last-run">Last Run</MenuItem>
            </Select>
          </FormControl>
          {reportMode === 'period' && (
            <FormControl variant="outlined" size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Time Period</InputLabel>
              <Select
                value={days}
                onChange={(e) => setDays(e.target.value as number)}
                label="Time Period"
              >
                <MenuItem value={7}>Last 7 Days</MenuItem>
                <MenuItem value={30}>Last 30 Days</MenuItem>
                <MenuItem value={90}>Last 90 Days</MenuItem>
                <MenuItem value={365}>Last 365 Days</MenuItem>
              </Select>
            </FormControl>
          )}
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={fetchReportData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={handleDownloadPDF}
            disabled={downloading || !reportData}
          >
            {downloading ? 'Generating...' : 'Download PDF'}
          </Button>
        </Box>
      </Box>

      {reportMode === 'last-run' && reportData && 'execution_id' in reportData && (
        <Box mb={3}>
          <Card>
            <CardContent>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="textSecondary">Execution ID</Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                    {reportData.execution_id}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="textSecondary">Test Suite</Typography>
                  <Typography variant="body1">
                    {reportData.test_suite_name || 'Unknown'}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="textSecondary">Status</Typography>
                  <Chip 
                    label={reportData.status} 
                    color={reportData.status === 'completed' ? 'success' : 'default'}
                    size="small"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="textSecondary">Completed At</Typography>
                  <Typography variant="body1">
                    {reportData.completed_at 
                      ? new Date(reportData.completed_at).toLocaleString()
                      : 'In Progress'}
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Box>
      )}

      <Box id="report-content">

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Executions
              </Typography>
              <Typography variant="h4">
                {summary.total_executions}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Tests
              </Typography>
              <Typography variant="h4">
                {summary.total_tests}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Pass Rate
              </Typography>
              <Typography variant="h4" color={summary.pass_rate >= 80 ? 'success.main' : 'error.main'}>
                {summary.pass_rate.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Security Findings
              </Typography>
              <Typography variant="h4" color="warning.main">
                {security_findings.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts Row 1 */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Status Distribution
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={statusChartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry: any) => {
                      if (entry && entry.name && entry.percent !== undefined) {
                        return `${entry.name}: ${(entry.percent * 100).toFixed(0)}%`;
                      }
                      return '';
                    }}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Type Breakdown
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={testTypeChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#2196f3" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Daily Trends - Only show for period reports */}
      {hasDailyTrends && (
        <Card sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Daily Test Execution Trends
            </Typography>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={dailyChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="Passed" stroke="#4caf50" strokeWidth={2} />
                <Line type="monotone" dataKey="Failed" stroke="#f44336" strokeWidth={2} />
                <Line type="monotone" dataKey="Errors" stroke="#ff9800" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Endpoint Performance */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Top Endpoints by Test Count
          </Typography>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={endpointChartData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={200} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Passed" stackId="a" fill="#4caf50" />
              <Bar dataKey="Failed" stackId="a" fill="#f44336" />
              <Bar dataKey="Errors" stackId="a" fill="#ff9800" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Security Findings */}
      {security_findings.length > 0 && (
        <Card sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Security Findings ({security_findings.length})
            </Typography>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Test Name</TableCell>
                    <TableCell>Endpoint</TableCell>
                    <TableCell>Method</TableCell>
                    <TableCell>Issue</TableCell>
                    <TableCell>Date</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {security_findings.slice(0, 20).map((finding, index) => (
                    <TableRow key={index}>
                      <TableCell>{finding.test_name}</TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {finding.endpoint}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={finding.method} size="small" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="error">
                          {finding.error}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {new Date(finding.date).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Endpoint Performance Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Endpoint Performance Details
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Method</TableCell>
                  <TableCell>Endpoint</TableCell>
                  <TableCell>Total</TableCell>
                  <TableCell>Passed</TableCell>
                  <TableCell>Failed</TableCell>
                  <TableCell>Errors</TableCell>
                  <TableCell>Pass Rate</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {endpoint_performance.slice(0, 20).map((endpoint, index) => {
                  const passRate = endpoint.total > 0 
                    ? (endpoint.passed / endpoint.total * 100).toFixed(1)
                    : '0.0';
                  return (
                    <TableRow key={index}>
                      <TableCell>
                        <Chip 
                          label={endpoint.method} 
                          size="small"
                          color={endpoint.method === 'GET' ? 'success' : 'primary'}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {endpoint.endpoint}
                        </Typography>
                      </TableCell>
                      <TableCell>{endpoint.total}</TableCell>
                      <TableCell>
                        <Chip label={endpoint.passed} size="small" color="success" />
                      </TableCell>
                      <TableCell>
                        <Chip label={endpoint.failed} size="small" color="error" />
                      </TableCell>
                      <TableCell>
                        <Chip label={endpoint.errors} size="small" color="warning" />
                      </TableCell>
                      <TableCell>
                        <Typography 
                          variant="body2" 
                          color={parseFloat(passRate) >= 80 ? 'success.main' : 'error.main'}
                          fontWeight="bold"
                        >
                          {passRate}%
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
      </Box>
    </Box>
  );
};

export default Reports;
