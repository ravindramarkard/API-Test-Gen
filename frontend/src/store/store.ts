import { configureStore } from '@reduxjs/toolkit';
import projectsReducer from './slices/projectsSlice';
import configReducer from './slices/configSlice';
import testReducer from './slices/testSlice';

export const store = configureStore({
  reducer: {
    projects: projectsReducer,
    config: configReducer,
    tests: testReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;




