import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuditLogPage from '../AuditLogPage';
import { getAuditLogs, type AuditLog } from '../AuditService';

vi.mock('../AuditService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../AuditService')>()),
  getAuditLogs: vi.fn(),
}));
const fetchLogs = vi.mocked(getAuditLogs);

const refund: AuditLog = {
  id: 'log-1',
  actorId: 'admin-7',
  action: 'refund_payment',
  resource: 'payment',
  resourceId: 'pay-1',
  oldValues: null,
  newValues: '{"amount_cents": 500}',
  ipAddress: '203.0.113.9',
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36',
  service: 'payment_service',
  createdAt: '2026-10-10T09:00:00Z',
};

describe('AuditLogPage', () => {
  beforeEach(() => {
    fetchLogs.mockReset();
    fetchLogs.mockResolvedValue({ data: [refund], total: 1, page: 1 });
  });

  it('shows which service recorded each entry and the client the admin used', async () => {
    render(<AuditLogPage />);

    expect(await screen.findByText('refund_payment')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Service' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Payments' })).toBeInTheDocument();
    expect(screen.getByText('203.0.113.9')).toBeInTheDocument();
    // The summary is shown; the full user agent is kept for the tooltip.
    expect(screen.getByText('Chrome on Windows')).toHaveAttribute('title', refund.userAgent);
  });

  it('filters by service', async () => {
    render(<AuditLogPage />);
    await screen.findByText('refund_payment');

    fireEvent.change(screen.getByLabelText('Service'), { target: { value: 'dispute_service' } });

    await waitFor(() =>
      expect(fetchLogs).toHaveBeenLastCalledWith({ service: 'dispute_service', page: 1, perPage: 25 }),
    );
  });
});
