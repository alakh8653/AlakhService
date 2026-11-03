import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { configureStore } from '@reduxjs/toolkit';
import { Provider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReportsPage from '../ReportsPage';
import * as service from '../../services/reportService';

vi.mock('../../components/Toast', () => ({ useToast: () => toast }));
const toast = vi.fn();

const report = (profit: number): service.ShopReport => ({
  label: 'November 2026',
  from: '2026-11-01',
  to: '2026-11-30',
  bookings: 3,
  gross: 1500,
  cash: 500,
  online: 1000,
  commission: 150,
  gst: 27,
  earned: 1323,
  other_income: 0,
  expenses: 1323 - profit,
  profit,
  tips: 0,
  profit_change_percent: 12.5,
  expenses_by_category: [],
  breakdown: [],
  note: 'Profit counts only what is recorded here.',
});

const settings = { daily: true, weekly: true, monthly: true, yearly: true, email: true, whatsapp: false };

function show() {
  const store = configureStore({ reducer: { auth: () => ({ shop: { id: 'shop-1' } }) } });
  return render(
    <Provider store={store}>
      <ReportsPage />
    </Provider>,
  );
}

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    toast.mockReset();
    vi.spyOn(service, 'getEntries').mockResolvedValue([]);
    vi.spyOn(service, 'getReportSettings').mockResolvedValue(settings);
  });

  it('shows the profit and asks again for each period', async () => {
    const get = vi.spyOn(service, 'getReport').mockResolvedValue(report(1000));
    show();
    expect(await screen.findByText(/^Profit ₹/)).toBeTruthy();
    expect(screen.getByText('Up 12.5% on the period before')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Yearly' }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('shop-1', 'yearly'));
  });

  it('calls a loss a loss', async () => {
    vi.spyOn(service, 'getReport').mockResolvedValue(report(-200));
    show();
    expect(await screen.findByText(/^Loss /)).toBeTruthy();
  });

  it('adds an expense and refuses one with no amount', async () => {
    vi.spyOn(service, 'getReport').mockResolvedValue(report(1000));
    const add = vi.spyOn(service, 'addEntry').mockResolvedValue({ id: 'e1', kind: 'EXPENSE', category: 'MATERIALS', amount: 450, on_date: '2026-11-03', note: null });
    show();
    const button = await screen.findByRole('button', { name: 'Add' });
    fireEvent.click(button);
    expect(await screen.findByText('Enter an amount.')).toBeTruthy();
    expect(add).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Amount (₹)'), { target: { value: '450' } });
    fireEvent.click(button);
    await waitFor(() => expect(add).toHaveBeenCalledWith('shop-1', { kind: 'EXPENSE', category: 'MATERIALS', amount: 450, note: undefined }));
  });

  it('says truthfully where a report went', async () => {
    vi.spyOn(service, 'getReport').mockResolvedValue(report(1000));
    vi.spyOn(service, 'sendReportNow').mockResolvedValue(['app']);
    show();
    fireEvent.click(await screen.findByRole('button', { name: 'Send me this report now' }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.stringContaining("aren't set up")));
  });

  it('turns whatsapp on only when the owner does', async () => {
    vi.spyOn(service, 'getReport').mockResolvedValue(report(1000));
    const save = vi.spyOn(service, 'saveReportSettings').mockResolvedValue({ ...settings, whatsapp: true });
    show();
    const box = (await screen.findByLabelText(/On WhatsApp/)) as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    await waitFor(() => expect(save).toHaveBeenCalledWith('shop-1', { ...settings, whatsapp: true }));
  });
});
