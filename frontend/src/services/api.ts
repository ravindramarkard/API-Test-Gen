import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL, // Remove trailing slash
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Remove Content-Type for FormData - let browser set it with boundary
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    // Ensure baseURL is always used - if url starts with /, it's treated as absolute
    if (config.url && config.url.startsWith('/') && config.baseURL) {
      // Remove leading slash to ensure baseURL is used
      config.url = config.url.substring(1);
    }
    // Debug: Log the actual URL being used
    console.log('Request URL:', config.url);
    console.log('Base URL:', config.baseURL);
    console.log('Full URL:', config.url ? `${config.baseURL}/${config.url}` : config.baseURL);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('token');
    }
    return Promise.reject(error);
  }
);

export default api;

