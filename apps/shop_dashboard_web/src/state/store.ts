import { configureStore } from '@reduxjs/toolkit';
import authReducer from './authSlice';
import bookingReducer from './bookingSlice';
import { rememberRefreshToken } from '../services/refreshToken';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    bookings: bookingReducer,
  },
});

// Keep the (rotating) refresh token in storage so a reload does not sign the owner out.
let lastRefreshToken = store.getState().auth.refreshToken;
store.subscribe(() => {
  const token = store.getState().auth.refreshToken;
  if (token !== lastRefreshToken) {
    lastRefreshToken = token;
    rememberRefreshToken(token);
  }
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
