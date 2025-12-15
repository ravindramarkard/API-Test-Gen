import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
} from '@mui/material';
import { CloudUpload, Dashboard, Settings, Assessment } from '@mui/icons-material';

const Navbar: React.FC = () => {
  const location = useLocation();

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          API Test Generation Platform
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            color="inherit"
            component={Link}
            to="/"
            startIcon={<Dashboard />}
            variant={location.pathname === '/' ? 'outlined' : 'text'}
          >
            Dashboard
          </Button>
          <Button
            color="inherit"
            component={Link}
            to="/upload"
            startIcon={<CloudUpload />}
            variant={location.pathname === '/upload' ? 'outlined' : 'text'}
          >
            Upload
          </Button>
          <Button
            color="inherit"
            component={Link}
            to="/reports"
            startIcon={<Assessment />}
            variant={location.pathname.startsWith('/reports') ? 'outlined' : 'text'}
          >
            Reports
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;

