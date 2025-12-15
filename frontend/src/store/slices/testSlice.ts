import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';

interface TestState {
  testSuite: any | null;
  execution: any | null;
  loading: boolean;
  error: string | null;
}

const initialState: TestState = {
  testSuite: null,
  execution: null,
  loading: false,
  error: null,
};

export const generateTests = createAsyncThunk(
  'tests/generateTests',
  async ({ 
    projectId, 
    format, 
    selectedEndpoints 
  }: { 
    projectId: string; 
    format?: string;
    selectedEndpoints?: Array<{ path: string; method: string }>;
  }) => {
    const requestBody = selectedEndpoints && selectedEndpoints.length > 0
      ? { selected_endpoints: selectedEndpoints }
      : undefined;
    
    const response = await api.post(
      `/generate/${projectId}?test_format=${format || 'pytest'}`,
      requestBody
    );
    return response.data;
  }
);

export const executeTests = createAsyncThunk(
  'tests/executeTests',
  async (testSuiteId: string) => {
    const response = await api.post(`/execute/${testSuiteId}`);
    return response.data;
  }
);

export const fetchExecution = createAsyncThunk(
  'tests/fetchExecution',
  async (executionId: string) => {
    const response = await api.get(`/execute/${executionId}`);
    return response.data;
  }
);

export const fetchLatestTestSuite = createAsyncThunk(
  'tests/fetchLatestTestSuite',
  async (projectId: string) => {
    try {
      const response = await api.get(`/generate/project/${projectId}/latest`);
      return response.data;
    } catch (error: any) {
      // If 404, return null (no test suite exists)
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }
);

const testSlice = createSlice({
  name: 'tests',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(generateTests.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(generateTests.fulfilled, (state, action) => {
        state.loading = false;
        state.testSuite = action.payload;
      })
      .addCase(generateTests.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to generate tests';
      })
      .addCase(executeTests.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(executeTests.fulfilled, (state, action) => {
        state.loading = false;
        state.execution = action.payload;
      })
      .addCase(executeTests.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to execute tests';
      })
      .addCase(fetchExecution.fulfilled, (state, action) => {
        state.execution = action.payload;
      })
      .addCase(fetchLatestTestSuite.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchLatestTestSuite.fulfilled, (state, action) => {
        state.loading = false;
        state.testSuite = action.payload;
      })
      .addCase(fetchLatestTestSuite.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch test suite';
        state.testSuite = null;
      });
  },
});

export const { clearError } = testSlice.actions;
export default testSlice.reducer;

