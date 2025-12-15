import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';

export interface Config {
  config_id?: string;
  base_url: string;
  auth_type?: string;
  llm_provider?: string;
  llm_model?: string;
  llm_endpoint?: string;
  has_auth?: boolean;
  has_llm_key?: boolean;
}

interface ConfigState {
  config: Config | null;
  loading: boolean;
  error: string | null;
}

const initialState: ConfigState = {
  config: null,
  loading: false,
  error: null,
};

export const fetchConfig = createAsyncThunk(
  'config/fetchConfig',
  async (projectId: string) => {
    const response = await api.get(`/config/${projectId}`);
    return response.data;
  }
);

export const saveConfig = createAsyncThunk(
  'config/saveConfig',
  async ({ projectId, config }: { projectId: string; config: any }) => {
    const response = await api.post(`/config/${projectId}`, config);
    return response.data;
  }
);

const configSlice = createSlice({
  name: 'config',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchConfig.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchConfig.fulfilled, (state, action) => {
        state.loading = false;
        state.config = action.payload;
      })
      .addCase(fetchConfig.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch config';
      })
      .addCase(saveConfig.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(saveConfig.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(saveConfig.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to save config';
      });
  },
});

export const { clearError } = configSlice.actions;
export default configSlice.reducer;


