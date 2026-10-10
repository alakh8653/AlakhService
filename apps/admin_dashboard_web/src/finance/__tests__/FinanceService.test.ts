import adminApiClient from '../../apiClient';
import { getRevenueReport, getSettlements } from '../FinanceService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);

describe('FinanceService', () => {
  beforeEach(() => get.mockReset());

  it('converts settlement amounts from cents and passes filters', async () => {
    get.mockResolvedValue({
      data: {
        data: [{ id: 'e1', payment_id: 'p1', booking_id: 'b1', payee_id: 'prov', amount_cents: 123_45, currency: 'INR', status: 'HELD', held_at: '2026-10-01T00:00:00Z', released_at: null }],
        total: 1,
        page: 2,
      },
    });
    const result = await getSettlements({ status: 'HELD', page: 2, perPage: 20 });
    expect(get).toHaveBeenCalledWith('/admin/finance/settlements', { params: { status: 'HELD', page: 2, per_page: 20 } });
    expect(result.data[0]).toMatchObject({ payeeId: 'prov', amount: 123.45, status: 'HELD' });
  });

  it('converts the revenue report from cents', async () => {
    get.mockResolvedValue({
      data: {
        currency: 'INR', gross_cents: 35_000, refunds_cents: 2_000, net_cents: 33_000, payments: 3,
        series: [{ date: '2026-10-01', gross_cents: 15_000, refunds_cents: 0, net_cents: 15_000, payments: 2 }],
      },
    });
    const report = await getRevenueReport({ dateFrom: '2026-10-01', dateTo: '2026-10-04' });
    expect(get).toHaveBeenCalledWith('/admin/finance/revenue', { params: { date_from: '2026-10-01', date_to: '2026-10-04' } });
    expect(report).toMatchObject({ gross: 350, refunds: 20, net: 330, payments: 3 });
    expect(report.series[0]).toEqual({ date: '2026-10-01', gross: 150, refunds: 0, net: 150, payments: 2 });
  });
});
