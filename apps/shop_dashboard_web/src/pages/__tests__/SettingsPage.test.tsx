import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import SettingsPage from '../SettingsPage';
import { updateShop } from '../../services/shopService';
import type { Shop } from '../../types';

vi.mock('../../services/shopService', () => ({ updateShop: vi.fn() }));

const shop: Shop = {
  id: 's1',
  ownerId: 'u1',
  name: 'Demo Salon',
  category: 'salon',
  description: null,
  city: 'Pune',
  address: '12 MG Road',
  phone: null,
  email: null,
  latitude: null,
  longitude: null,
  ratingAvg: 0,
  ratingCount: 0,
  isActive: true,
  isVerified: false,
  createdAt: '',
};

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop(shop));
  render(
    <Provider store={store}>
      <SettingsPage />
    </Provider>,
  );
}

describe('SettingsPage map location', () => {
  beforeEach(() => vi.clearAllMocks());

  it('saves the coordinates customers get directions to', async () => {
    vi.mocked(updateShop).mockImplementation(async (_id, update) => ({ ...shop, ...update }) as Shop);
    renderPage();
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '18.5204' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '73.8567' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalled());
    expect(vi.mocked(updateShop).mock.calls[0][1]).toMatchObject({ latitude: 18.5204, longitude: 73.8567 });
  });

  it('fills them in from this device', async () => {
    const getCurrentPosition = vi.fn((ok: PositionCallback) =>
      ok({ coords: { latitude: 18.52041234, longitude: 73.85671234 } } as GeolocationPosition),
    );
    Object.defineProperty(navigator, 'geolocation', { value: { getCurrentPosition }, configurable: true });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /Use my current location/ }));
    await waitFor(() => expect(screen.getByLabelText('Latitude')).toHaveValue('18.520412'));
    expect(screen.getByLabelText('Longitude')).toHaveValue('73.856712');
  });

  it('refuses half a location or impossible values', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '18.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    expect(await screen.findByText('Enter both latitude and longitude, or neither')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '123' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '73.8' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    expect(await screen.findByText('Between -90 and 90')).toBeInTheDocument();
    expect(updateShop).not.toHaveBeenCalled();
  });
});
