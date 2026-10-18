import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { format, subDays } from 'date-fns';
import RevenueReportPage from '../RevenueReportPage';
import SettlementsPage from '../SettlementsPage';
import { getRevenueReport, getSettlements, type RevenueReport } from '../FinanceService';

vi.mock('../FinanceService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../FinanceService')>()),
  getRevenueReport: vi.fn(),
  getSettlements: vi.fn(),
}));
vi.mock('../../users/accountNames', () => ({
  useAccounts: () => ({ 'prov-1': { id: 'prov-1', name: 'Ravi Technician', email: 'tech@example.com', phone: null } }),
}));
// recharts needs layout APIs jsdom lacks; the chart itself is not under test.
vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: unknown }) => <div data-testid="chart">{children as never}</div>,
}));

const report = (over: Partial<RevenueReport> = {}): RevenueReport => ({
  currency: 'INR',
  gross: 123456.5,
  refunds: 500,
  net: 122956.5,
  payments: 1520,
  series: [{ date: '2026-10-17', gross: 123456.5, refunds: 500, net: 122956.5, payments: 1520 }],
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRevenueReport).mockResolvedValue(report());
});

describe('RevenueReportPage', () => {
  it('shows totals with Indian grouping', async () => {
    render(<RevenueReportPage />);
    expect(await screen.findByText('₹1,23,456.50')).toBeInTheDocument();
    expect(screen.getByText('1,520')).toBeInTheDocument();
  });

  it('offers quick ranges', async () => {
    render(<RevenueReportPage />);
    await screen.findByText('₹1,23,456.50');
    expect(screen.getByRole('button', { name: 'Last 30 days' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Last 7 days' }));
    const today = format(new Date(), 'yyyy-MM-dd');
    await waitFor(() =>
      expect(getRevenueReport).toHaveBeenLastCalledWith({ dateFrom: format(subDays(new Date(), 6), 'yyyy-MM-dd'), dateTo: today }),
    );
  });

  it('says so when there is nothing to chart', async () => {
    vi.mocked(getRevenueReport).mockResolvedValue(report({ gross: 0, refunds: 0, net: 0, payments: 0, series: [] }));
    render(<RevenueReportPage />);
    expect(await screen.findByText('No payments or refunds in this period.')).toBeInTheDocument();
  });

  it('shows the API’s reason when the report fails', async () => {
    vi.mocked(getRevenueReport).mockRejectedValue({ response: { data: { detail: 'Report range is limited to 366 days' } } });
    render(<RevenueReportPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Report range is limited to 366 days');
  });

  it('checks the range before asking the API', async () => {
    render(<RevenueReportPage />);
    await screen.findByText('₹1,23,456.50');
    vi.mocked(getRevenueReport).mockClear();
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2020-01-01' } });
    expect(screen.getByRole('alert')).toHaveTextContent('Choose at most 366 days.');
    expect(getRevenueReport).not.toHaveBeenCalled();
  });
});

describe('SettlementsPage', () => {
  it('names the provider and has an "All" filter', async () => {
    vi.mocked(getSettlements).mockResolvedValue({
      data: [
        {
          id: 's1',
          paymentId: 'p1',
          bookingId: 'b1',
          payeeId: 'prov-1',
          amount: 2500,
          currency: 'INR',
          status: 'HELD',
          heldAt: '2026-10-16T06:30:00Z',
          releasedAt: null,
        },
      ],
      total: 1,
      page: 1,
    });
    render(<SettlementsPage />);
    expect(await screen.findByText('Ravi Technician')).toBeInTheDocument();
    expect(screen.getByText('₹2,500.00')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Paid out' }));
    await waitFor(() => expect(getSettlements).toHaveBeenLastCalledWith({ status: 'RELEASED', page: 1, perPage: 20 }));
  });
});
