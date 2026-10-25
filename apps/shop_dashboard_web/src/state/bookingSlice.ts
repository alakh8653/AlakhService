import { createAsyncThunk, createSlice, PayloadAction } from '@reduxjs/toolkit';
import { getShopBookings, type BookingFilters } from '../services/bookingService';
import { apiErrorMessage } from '../services/format';
import type { Booking } from '../types';

interface BookingState {
  bookings: Booking[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
  isLoading: boolean;
  error: string | null;
  activeFilters: BookingFilters;
  /** The latest list request; answers to older ones (a filter tapped since) are dropped. */
  requestId: string | null;
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
  requestId: null,
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
      .addCase(fetchBookings.pending, (state, action) => {
        state.requestId = action.meta.requestId;
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchBookings.fulfilled, (state, action) => {
        if (action.meta.requestId !== state.requestId) return;
        state.isLoading = false;
        state.bookings = action.payload.data;
        state.total = action.payload.total;
        state.page = action.payload.page;
        state.perPage = action.payload.perPage;
        state.totalPages = action.payload.totalPages;
      })
      .addCase(fetchBookings.rejected, (state, action) => {
        if (action.meta.requestId !== state.requestId) return;
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { setFilters, updateBookingInList, clearBookingError } = bookingSlice.actions;

export default bookingSlice.reducer;
