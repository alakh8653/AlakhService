import { createAsyncThunk, createSlice, PayloadAction } from '@reduxjs/toolkit';
import {
  getShopBookings,
  updateBookingStatus,
  cancelBooking,
  type BookingFilters,
} from '../services/bookingService';
import { apiErrorMessage } from '../services/format';
import type { Booking, BookingStatus } from '../types';

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

interface ShopState {
  auth: { shop: { id: string } | null };
}

function currentShopId(getState: () => unknown): string {
  const shop = (getState() as ShopState).auth.shop;
  if (!shop) throw new Error('No shop selected');
  return shop.id;
}

export const fetchBookings = createAsyncThunk(
  'bookings/fetchAll',
  async (filters: BookingFilters, { getState, rejectWithValue }) => {
    try {
      return await getShopBookings(currentShopId(getState), filters);
    } catch (err) {
      return rejectWithValue(apiErrorMessage(err, 'Could not load bookings'));
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
      return rejectWithValue(apiErrorMessage(err, 'Could not update the booking'));
    }
  },
);

export const cancelBookingThunk = createAsyncThunk(
  'bookings/cancel',
  async ({ id, reason }: { id: string; reason: string }, { rejectWithValue }) => {
    try {
      return await cancelBooking(id, reason);
    } catch (err) {
      return rejectWithValue(apiErrorMessage(err, 'Could not cancel the booking'));
    }
  },
);

function replaceBooking(state: BookingState, booking: Booking) {
  const index = state.bookings.findIndex((b) => b.id === booking.id);
  if (index !== -1) {
    state.bookings[index] = booking;
  }
}

const bookingSlice = createSlice({
  name: 'bookings',
  initialState,
  reducers: {
    setFilters(state, action: PayloadAction<BookingFilters>) {
      state.activeFilters = action.payload;
    },
    updateBookingInList(state, action: PayloadAction<Booking>) {
      replaceBooking(state, action.payload);
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
      .addCase(fetchBookings.fulfilled, (state, action) => {
        state.isLoading = false;
        state.bookings = action.payload.data;
        state.total = action.payload.total;
        state.page = action.payload.page;
        state.perPage = action.payload.perPage;
        state.totalPages = action.payload.totalPages;
      })
      .addCase(fetchBookings.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      .addCase(changeBookingStatus.fulfilled, (state, action) => {
        replaceBooking(state, action.payload);
      })
      .addCase(changeBookingStatus.rejected, (state, action) => {
        state.error = action.payload as string;
      })
      .addCase(cancelBookingThunk.fulfilled, (state, action) => {
        replaceBooking(state, action.payload);
      })
      .addCase(cancelBookingThunk.rejected, (state, action) => {
        state.error = action.payload as string;
      });
  },
});

export const { setFilters, updateBookingInList, clearBookingError } = bookingSlice.actions;

export default bookingSlice.reducer;
