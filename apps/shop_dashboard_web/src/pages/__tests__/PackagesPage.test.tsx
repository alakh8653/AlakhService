import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import { ToastProvider } from '../../components/Toast';
import PackagesPage from '../PackagesPage';
import * as packages from '../../services/packageService';
import * as shops from '../../services/shopService';
import type { Service, Shop } from '../../types';

const shop = { id: 's1', ownerId: 'u1', name: 'Asha Salon', isVerified: true } as Shop;
const haircut = { id: 'svc1', shopId: 's1', categoryId: null, name: 'Haircut', description: null, priceCents: 30000, durationMinutes: 30, isActive: true, createdAt: '' } as Service;
const onSale: packages.ServicePackage = { id: 'pk1', shopId: 's1', serviceId: 'svc1', name: '5 haircuts', visits: 5, priceCents: 120000, validDays: 90, isActive: true };

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop(shop));
  render(
    <Provider store={store}>
      <ToastProvider>
        <PackagesPage />
      </ToastProvider>
    </Provider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(shops, 'getServices').mockResolvedValue([haircut]);
});

describe('PackagesPage', () => {
  it('adds a package of one of the shop services and shows what customers save', async () => {
    vi.spyOn(packages, 'getPackages').mockResolvedValue([]);
    const create = vi.spyOn(packages, 'createPackage').mockResolvedValue(onSale);
    renderPage();
    expect(await screen.findByText('No packages yet.')).toBeInTheDocument();

    const form = screen.getByRole('form', { name: 'New package' });
    await waitFor(() => expect(within(form).getByRole('option', { name: 'Haircut (₹300)' })).toBeInTheDocument());
    fireEvent.change(within(form).getByLabelText('Service'), { target: { value: 'svc1' } });
    fireEvent.change(within(form).getByLabelText('Name customers see'), { target: { value: '5 haircuts' } });
    fireEvent.change(within(form).getByLabelText('Price (₹)'), { target: { value: '1200' } });
    expect(within(form).getByText('Customers save ₹300 against ₹1,500.')).toBeInTheDocument();
    fireEvent.click(within(form).getByRole('button', { name: 'Add package' }));

    await waitFor(() => expect(create).toHaveBeenCalledWith('s1', { serviceId: 'svc1', name: '5 haircuts', visits: 5, priceCents: 120000, validDays: 90 }));
    const list = await screen.findByRole('list', { name: 'Your packages' });
    expect(within(list).getByText(/Haircut · 5 visits · ₹1,200 · valid 90 days/)).toBeInTheDocument();
  });

  it('takes a package off sale', async () => {
    vi.spyOn(packages, 'getPackages').mockResolvedValue([onSale]);
    const toggle = vi.spyOn(packages, 'setPackageActive').mockResolvedValue({ ...onSale, isActive: false });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Take off sale' }));
    await waitFor(() => expect(toggle).toHaveBeenCalledWith('pk1', false));
    expect(await screen.findByText('Off sale')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Put on sale' })).toBeInTheDocument();
  });
});
