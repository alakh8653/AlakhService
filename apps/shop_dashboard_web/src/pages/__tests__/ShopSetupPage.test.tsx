import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import ShopSetupPage from '../ShopSetupPage';
import { updateShop } from '../../services/shopService';
import type { Shop } from '../../types';

const createShop = vi.fn();
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', name: 'Asha' }, createShop, logout: vi.fn() }),
}));
vi.mock('../../services/shopService', () => ({ updateShop: vi.fn() }));

const created = { id: 's1', name: 'Asha Salon', guaranteeDays: 7 } as Shop;

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ShopSetupPage />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

function fillIn() {
  fireEvent.change(screen.getByLabelText('Shop name'), { target: { value: 'Asha Salon' } });
  fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'salon' } });
  fireEvent.change(screen.getByLabelText('City'), { target: { value: 'Pune' } });
}

describe('ShopSetupPage free-fix guarantee', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createShop.mockResolvedValue(created);
  });

  it('is set on the new shop, a week unless changed', async () => {
    vi.mocked(updateShop).mockResolvedValue({ ...created, guaranteeDays: 14 });
    const store = renderPage();
    expect(screen.getByLabelText('Free-fix guarantee (days)')).toHaveValue(7);
    fillIn();
    fireEvent.change(screen.getByLabelText('Free-fix guarantee (days)'), { target: { value: '14' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create shop' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalledWith('s1', { guarantee_days: 14 }));
    expect(createShop.mock.calls[0][0]).not.toHaveProperty('guaranteeDays');
    await waitFor(() => expect(store.getState().auth.shop?.guaranteeDays).toBe(14));
  });

  it('still opens the shop when the guarantee cannot be saved', async () => {
    vi.mocked(updateShop).mockRejectedValue(new Error('Not Found'));
    renderPage();
    fillIn();
    fireEvent.click(screen.getByRole('button', { name: 'Create shop' }));
    await waitFor(() => expect(updateShop).toHaveBeenCalled());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
