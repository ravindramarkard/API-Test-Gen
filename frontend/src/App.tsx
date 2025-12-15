import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Container } from '@mui/material';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import ProjectDetail from './pages/ProjectDetail';
import Config from './pages/Config';
import Results from './pages/Results';
import TestSuite from './pages/TestSuite';
import Reports from './pages/Reports';

function App() {
  return (
    <div className="App">
      <Navbar />
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/projects/:projectId/config" element={<Config />} />
          <Route path="/test-suites/:testSuiteId" element={<TestSuite />} />
          <Route path="/executions/:executionId" element={<Results />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/reports/project/:projectId" element={<Reports />} />
          <Route path="/reports/test-suite/:testSuiteId" element={<Reports />} />
        </Routes>
      </Container>
    </div>
  );
}

export default App;

