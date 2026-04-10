import {
  createAsyncThunk,
  createSlice,
  PayloadAction,
} from '@reduxjs/toolkit';
import {
  getBookings,
  updateBookingStatus,
  cancelBooking,
  type BookingFilters,
} from '../services/bookingService';
import type { Booking, BookingStatus, PaginatedResponse } from '../types';

interface BookingState {
  bookings: Booking[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  isLoading: boolean;
  error: string | null;
  activeFilters: BookingFilters;
}

const initialState: BookingState = {
  bookings: [],
  total: 0,
  page: 1,
  perPage: 20,
  totalPages: 0,
  isLoading: false,
  error: null,
  activeFilters: {},
};

export const fetchBookings = createAsyncThunk(
  'bookings/fetchAll',
  async (filters: BookingFilters, { rejectWithValue }) => {
    try {
      return await getBookings(filters);
    } catch (err) {
      return rejectWithValue((err as Error).message);
    }
  },
);

export const changeBookingStatus = createAsyncThunk(
  'bookings/changeStatus',
  async (
    { id, status, reason }: { id: string; status: BookingStatus; reason?: string },
    { rejectWithValue },
  ) => {
    try {
      return await updateBookingStatus(id, status, reason);
    } catch (err) {
      return rejectWithValue((err as Error).message);
    }
  },
);

export const cancelBookingThunk = createAsyncThunk(
  'bookings/cancel',
  async (
    { id, reason }: { id: string; reason: string },
    { rejectWithValue },
  ) => {
    try {
      return await cancelBooking(id, reason);
    } catch (err) {
      return rejectWithValue((err as Error).message);
    }
  },
);

const bookingSlice = createSlice({
  name: 'bookings',
  initialState,
  reducers: {
    setFilters(state, action: PayloadAction<BookingFilters>) {
      state.activeFilters = action.payload;
    },
    updateBookingInList(state, action: PayloadAction<Booking>) {
      const index = state.bookings.findIndex((b) => b.id === action.payload.id);
      if (index !== -1) {
        state.bookings[index] = action.payload;
      }
    },
    clearBookingError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchBookings.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(
        fetchBookings.fulfilled,
        (state, action: PayloadAction<PaginatedResponse<Booking>>) => {
          state.isLoading = false;
          state.bookings = action.payload.data;
          state.total = action.payload.total;
          state.page = action.payload.page;
          state.perPage = action.payload.perPage;
          state.totalPages = action.payload.totalPages;
        },
      )
      .addCase(fetchBookings.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      .addCase(changeBookingStatus.fulfilled, (state, action) => {
        const index = state.bookings.findIndex((b) => b.id === action.payload.id);
        if (index !== -1) {
          state.bookings[index] = action.payload;
        }
      })
      .addCase(cancelBookingThunk.fulfilled, (state, action) => {
        const index = state.bookings.findIndex((b) => b.id === action.payload.id);
        if (index !== -1) {
          state.bookings[index] = action.payload;
        }
      });
  },
});

export const { setFilters, updateBookingInList, clearBookingError } =
  bookingSlice.actions;

export default bookingSlice.reducer;
