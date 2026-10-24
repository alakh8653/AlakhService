import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import { ToastProvider } from '../../components/Toast';
import EarningsPage, { thisMonth } from '../EarningsPage';
import * as earnings from '../../services/earningsService';
import * as kyc from '../../services/kycService';
import type { Shop } from '../../types';

const shop = { id: 's1', ownerId: 'u1', name: 'Asha Salon', isVerified: true } as Shop;

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop(shop));
  render(
    <Provider store={store}>
      <ToastProvider>
        <EarningsPage />
      </ToastProvider>
    </Provider>,
  );
}

const summary: earnings.Earnings = {
  currency: 'INR', gross: 1000, commission: 100, gstOnCommission: 18, net: 882, pendingPayout: 882, paidOut: 0,
  items: [{ bookingId: 'booking-1234', paymentId: 'p1', completedAt: '2026-10-20T10:00:00Z', gross: 1000, commission: 100, gstOnCommission: 18, net: 882, payoutStatus: 'READY' }],
};

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(kyc, 'getPayoutDetails').mockResolvedValue(null);
});

describe('EarningsPage', () => {
  it('defaults to this month in IST', () => {
    expect(thisMonth(new Date('2026-10-31T20:00:00Z'))).toEqual({ from: '2026-11-01', to: '2026-11-01' });
    expect(thisMonth(new Date('2026-10-23T05:00:00Z'))).toEqual({ from: '2026-10-01', to: '2026-10-23' });
  });

  it('shows earnings after commission, payouts and refetches for new dates', async () => {
    const get = vi.spyOn(earnings, 'getEarnings').mockResolvedValue(summary);
    vi.spyOn(earnings, 'getPayouts').mockResolvedValue([
      { id: 'po1', periodFrom: '2026-10-01', periodTo: '2026-10-07', amount: 500.5, status: 'PAID', paidAt: '2026-10-08T00:00:00Z', reference: 'UTR123' },
    ]);
    renderPage();
    expect(await screen.findByText('Your earnings')).toBeInTheDocument();
    expect(screen.getAllByText('₹882.00').length).toBeGreaterThan(0);
    expect(screen.getByText('+ ₹18.00 GST')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Earnings by booking' });
    expect(within(table).getByText('Ready for payout')).toBeInTheDocument();
    expect(await screen.findByText('UTR123')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-09-01' } });
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('s1', '2026-09-01', expect.any(String)));
  });

  it('says earnings are not available yet when payment_service does not have them', async () => {
    vi.spyOn(earnings, 'getEarnings').mockRejectedValue({ response: { status: 404 } });
    vi.spyOn(earnings, 'getPayouts').mockRejectedValue({ response: { status: 404 } });
    renderPage();
    expect(await screen.findByText('Earnings are not available yet. Please check back soon.')).toBeInTheDocument();
    expect(await screen.findByText('Payout history is not available yet.')).toBeInTheDocument();
    // The payout details form still works.
    expect(await screen.findByRole('form', { name: 'Payout details' })).toBeInTheDocument();
  });
});

describe('PayoutDetailsForm', () => {
  it('validates bank details, then saves and shows the masked account', async () => {
    vi.spyOn(earnings, 'getEarnings').mockResolvedValue({ ...summary, items: [] });
    vi.spyOn(earnings, 'getPayouts').mockResolvedValue([]);
    const save = vi.spyOn(kyc, 'savePayoutDetails').mockResolvedValue({
      method: 'BANK', accountName: 'Asha Rao', accountNumber: 'XXXXXXXX9012', ifsc: 'HDFC0001234', upiId: null, updatedAt: null,
    });
    renderPage();
    const form = await screen.findByRole('form', { name: 'Payout details' });
    fireEvent.click(within(form).getByRole('button', { name: 'Save payout details' }));
    expect(await within(form).findByText('IFSC is 11 characters, like HDFC0001234')).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.change(within(form).getByLabelText('Account holder name'), { target: { value: 'Asha Rao' } });
    fireEvent.change(within(form).getByLabelText('IFSC'), { target: { value: 'hdfc0001234' } });
    fireEvent.change(within(form).getByLabelText('Account number'), { target: { value: '123456789012' } });
    fireEvent.change(within(form).getByLabelText('Re-enter account number'), { target: { value: '123456789013' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save payout details' }));
    expect(await within(form).findByText('The account numbers do not match')).toBeInTheDocument();

    fireEvent.change(within(form).getByLabelText('Re-enter account number'), { target: { value: '123456789012' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save payout details' }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith('s1', { method: 'BANK', accountName: 'Asha Rao', accountNumber: '123456789012', ifsc: 'HDFC0001234', upiId: '' }),
    );
    expect(await within(form).findByText(/account XXXXXXXX9012/)).toBeInTheDocument();
  });

  it('takes a UPI id instead', async () => {
    vi.spyOn(earnings, 'getEarnings').mockResolvedValue({ ...summary, items: [] });
    vi.spyOn(earnings, 'getPayouts').mockResolvedValue([]);
    const save = vi.spyOn(kyc, 'savePayoutDetails').mockResolvedValue({
      method: 'UPI', accountName: null, accountNumber: null, ifsc: null, upiId: 'asha@okicici', updatedAt: null,
    });
    renderPage();
    const form = await screen.findByRole('form', { name: 'Payout details' });
    fireEvent.click(within(form).getByLabelText('UPI'));
    fireEvent.change(within(form).getByLabelText('UPI id'), { target: { value: 'not-upi' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save payout details' }));
    expect(await within(form).findByText('Enter a UPI id like yourshop@okhdfcbank')).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText('UPI id'), { target: { value: 'asha@okicici' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save payout details' }));
    await waitFor(() => expect(save).toHaveBeenCalledWith('s1', expect.objectContaining({ method: 'UPI', upiId: 'asha@okicici' })));
  });
});
