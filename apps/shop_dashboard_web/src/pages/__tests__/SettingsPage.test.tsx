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

  it('offers the category list and saves a phone typed the Indian way', async () => {
    vi.mocked(updateShop).mockImplementation(async (_id, update) => ({ ...shop, ...update }) as Shop);
    renderPage();
    const category = screen.getByLabelText('Category');
    await waitFor(() => expect(category).toHaveValue('salon'));
    expect(screen.getByRole('option', { name: 'Car & bike repair' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Shop phone'), { target: { value: '98765 43210' } });
    expect(await screen.findByText('Unsaved changes')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalled());
    expect(vi.mocked(updateShop).mock.calls[0][1]).toMatchObject({ phone: '+919876543210', category: 'salon' });
    expect(await screen.findByText('Settings saved successfully.')).toBeInTheDocument();
  });

  it('links to the pin on a map once both coordinates are set', async () => {
    renderPage();
    expect(screen.queryByRole('link', { name: /Check this pin/ })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '18.5204' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '73.8567' } });
    const link = await screen.findByRole('link', { name: /Check this pin on Google Maps/ });
    expect(link.getAttribute('href')).toContain('query=18.5204%2C73.8567');
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

describe('SettingsPage free-fix guarantee', () => {
  beforeEach(() => vi.clearAllMocks());

  it('starts at a week and saves the days the owner picks', async () => {
    vi.mocked(updateShop).mockImplementation(async (_id, update) => ({ ...shop, guaranteeDays: update.guarantee_days }) as Shop);
    renderPage();
    const days = screen.getByLabelText('Free-fix guarantee (days)');
    await waitFor(() => expect(days).toHaveValue(7));
    expect(screen.getByText(/the customer can ask for a free fix within these days/)).toBeInTheDocument();
    fireEvent.change(days, { target: { value: '30' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalled());
    expect(vi.mocked(updateShop).mock.calls[0][1]).toMatchObject({ guarantee_days: 30 });
  });

  it('refuses more than 90 days', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Free-fix guarantee (days)'), { target: { value: '120' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    expect(await screen.findByText('A whole number of days from 0 to 90')).toBeInTheDocument();
    expect(updateShop).not.toHaveBeenCalled();
  });
});
