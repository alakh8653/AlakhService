import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import adminApiClient from '../../apiClient';
import CommissionPanel, { percentFrom } from '../CommissionPanel';
import PayoutsPanel from '../PayoutsPanel';
import {
  createPayoutBatch,
  downloadPayoutsCsv,
  getCommission,
  getPayouts,
  markPayoutPaid,
  setDefaultCommission,
  setShopCommission,
  type Payout,
} from '../FinanceService';

vi.mock('../FinanceService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../FinanceService')>()),
  getPayouts: vi.fn(),
  createPayoutBatch: vi.fn(),
  markPayoutPaid: vi.fn(),
  downloadPayoutsCsv: vi.fn(),
  getCommission: vi.fn(),
  setShopCommission: vi.fn(),
  setDefaultCommission: vi.fn(),
}));
vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), defaults: { baseURL: 'http://gw/api/v1' } } }));

const payout = (over: Partial<Payout> = {}): Payout => ({
  id: 'po-1',
  batchId: 'b-1',
  shopId: 'shop-1234567890',
  periodFrom: '2026-10-01',
  periodTo: '2026-10-22',
  amount: 41652.5,
  currency: 'INR',
  status: 'PENDING',
  paidAt: null,
  reference: null,
  createdAt: '2026-10-23T05:00:00Z',
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getPayouts).mockResolvedValue({ data: [payout()], total: 1, page: 1 });
  vi.mocked(getCommission).mockResolvedValue({
    defaultPercent: 10,
    configuredDefaultPercent: 10,
    gstPercent: 18,
    overrides: [{ shopId: 'shop-9', percent: 5, updatedAt: null }],
  });
});

describe('PayoutsPanel', () => {
  it('lists pending payouts and marks one paid with its bank reference', async () => {
    vi.mocked(markPayoutPaid).mockResolvedValue(payout({ status: 'PAID', reference: 'UTR1' }));
    render(<PayoutsPanel />);
    expect(await screen.findByText('₹41,652.50')).toBeInTheDocument();
    expect(getPayouts).toHaveBeenCalledWith({ status: 'PENDING', page: 1, perPage: 20 });
    fireEvent.click(screen.getByRole('button', { name: 'Mark paid…' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Mark paid' });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'UTR1' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(markPayoutPaid).toHaveBeenCalledWith('po-1', 'UTR1'));
    await waitFor(() => expect(getPayouts).toHaveBeenCalledTimes(2));
  });

  it('creates a batch for the chosen period and downloads the CSV', async () => {
    vi.mocked(createPayoutBatch).mockResolvedValue({ batchId: 'b-2', payouts: [payout()], total: 41652.5 });
    vi.mocked(downloadPayoutsCsv).mockResolvedValue(new Blob(['payout_id\n']));
    const createObjectURL = vi.fn(() => 'blob:x');
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    render(<PayoutsPanel />);
    await screen.findByText('₹41,652.50');
    fireEvent.change(screen.getByLabelText('Completed up to'), { target: { value: '2026-10-20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create payouts' }));
    await waitFor(() => expect(createPayoutBatch).toHaveBeenCalledWith('2026-10-20'));
    fireEvent.click(screen.getByRole('button', { name: 'Download pending (CSV)' }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled());
  });

  it('says so when payouts cannot be loaded', async () => {
    vi.mocked(getPayouts).mockRejectedValue(new Error('down'));
    render(<PayoutsPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load payouts.');
  });
});

describe('CommissionPanel', () => {
  it('shows the default and per-shop rates, and sets and removes a shop rate', async () => {
    vi.mocked(setShopCommission).mockResolvedValue();
    render(<CommissionPanel />);
    expect(await screen.findByText('shop-9')).toBeInTheDocument();
    expect(screen.getByText('10%')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Shop ID'), { target: { value: 'shop-1' } });
    fireEvent.change(screen.getByLabelText('Rate (%)'), { target: { value: '80' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set shop rate' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('between 0 and 50%');
    expect(setShopCommission).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Rate (%)'), { target: { value: '7.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set shop rate' }));
    await waitFor(() => expect(setShopCommission).toHaveBeenCalledWith('shop-1', 7.5));
    fireEvent.click(screen.getByRole('button', { name: 'Remove the rate for shop shop-9' }));
    await waitFor(() => expect(setShopCommission).toHaveBeenCalledWith('shop-9', null));
  });

  it('sets the default rate', async () => {
    vi.mocked(setDefaultCommission).mockResolvedValue();
    render(<CommissionPanel />);
    await screen.findByText('shop-9');
    fireEvent.change(screen.getByLabelText('New default (%)'), { target: { value: '12' } });
    fireEvent.click(screen.getByRole('button', { name: 'Set default' }));
    await waitFor(() => expect(setDefaultCommission).toHaveBeenCalledWith(12));
  });

  it('reads percentages', () => {
    expect(percentFrom('10')).toBe(10);
    expect(percentFrom('12.345')).toBe(12.35);
    expect(percentFrom('')).toBeNull();
    expect(percentFrom('-1')).toBeNull();
    expect(percentFrom('51')).toBeNull();
  });
});

describe('FinanceService payouts', () => {
  it('maps payouts and sends the batch period', async () => {
    const { createPayoutBatch: realCreate } = await vi.importActual<typeof import('../FinanceService')>('../FinanceService');
    vi.mocked(adminApiClient.post).mockResolvedValue({
      data: {
        batch_id: 'b-9',
        total_amount_cents: 123456,
        payouts: [
          {
            id: 'po',
            batch_id: 'b-9',
            shop_id: 's',
            period_from: null,
            period_to: '2026-10-22',
            amount_cents: 123456,
            currency: 'INR',
            status: 'PENDING',
            paid_at: null,
            reference: null,
            created_at: '2026-10-23T00:00:00Z',
          },
        ],
      },
    });
    const batch = await realCreate('2026-10-22');
    expect(adminApiClient.post).toHaveBeenCalledWith('/admin/payments/payouts/batches', { period_to: '2026-10-22' });
    expect(batch.total).toBe(1234.56);
    expect(batch.payouts[0]).toMatchObject({ batchId: 'b-9', shopId: 's', amount: 1234.56 });
  });

  it('downloads the CSV with the admin token', async () => {
    const { downloadPayoutsCsv: realDownload } = await vi.importActual<typeof import('../FinanceService')>('../FinanceService');
    localStorage.setItem('admin_token', 'tok');
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['x'])) });
    vi.stubGlobal('fetch', fetchMock);
    await realDownload('b-9');
    expect(fetchMock).toHaveBeenCalledWith('http://gw/api/v1/admin/payments/payouts/export.csv?batch_id=b-9', {
      headers: { Authorization: 'Bearer tok' },
    });
    fetchMock.mockResolvedValue({ ok: false, status: 503 });
    await expect(realDownload()).rejects.toThrow('Export failed (503)');
    vi.unstubAllGlobals();
    localStorage.removeItem('admin_token');
  });
});
