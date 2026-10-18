import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import AuditLogPage from '../AuditLogPage';
import { getAuditLogs, type AuditLog } from '../AuditService';

vi.mock('../AuditService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../AuditService')>()),
  getAuditLogs: vi.fn(),
}));
vi.mock('../../users/accountNames', () => ({
  useAccounts: () => ({ 'admin-7': { id: 'admin-7', name: 'Meera Iyer', email: 'meera@example.com', phone: null } }),
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

    expect(await screen.findByText('Refund payment')).toBeInTheDocument();
    expect(screen.getByText('Meera Iyer')).toBeInTheDocument();
    expect(screen.getByText('10 Oct 2026, 2:30:00 pm')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Service' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Payments' })).toBeInTheDocument();
    expect(screen.getByText('203.0.113.9')).toBeInTheDocument();
    // The summary is shown; the full user agent is kept for the tooltip.
    expect(screen.getByText('Chrome on Windows')).toHaveAttribute('title', refund.userAgent);
  });

  it('filters by service', async () => {
    render(<AuditLogPage />);
    await screen.findByText('Refund payment');

    fireEvent.change(screen.getByLabelText('Service'), { target: { value: 'dispute_service' } });

    await waitFor(() =>
      expect(fetchLogs).toHaveBeenLastCalledWith({ service: 'dispute_service', page: 1, perPage: 25 }),
    );
  });

  it('filters by action from a list of known actions', async () => {
    render(<AuditLogPage />);
    await screen.findByText('Refund payment');
    fireEvent.change(screen.getByLabelText('Action'), { target: { value: 'ban_user' } });
    await waitFor(() => expect(fetchLogs).toHaveBeenLastCalledWith({ action: 'ban_user', page: 1, perPage: 25 }));
  });

  it('waits for the admin id to be typed before searching, and can clear all filters', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<AuditLogPage />);
      await screen.findByText('Refund payment');
      fireEvent.change(screen.getByLabelText('Admin user ID'), { target: { value: 'admin-7' } });
      expect(fetchLogs).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(500);
      await waitFor(() => expect(fetchLogs).toHaveBeenLastCalledWith({ actorId: 'admin-7', page: 1, perPage: 25 }));
      expect(fetchLogs).toHaveBeenCalledTimes(2);
      fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
      expect(screen.getByLabelText('Admin user ID')).toHaveValue('');
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows what changed when an entry is opened', async () => {
    render(<AuditLogPage />);
    fireEvent.click(await screen.findByRole('row', { name: /Refund payment by Meera Iyer/ }));
    const dialog = screen.getByRole('dialog', { name: 'Audit entry' });
    expect(within(dialog).getByText(/"amount_cents": 500/)).toBeInTheDocument();
    expect(within(dialog).getByText('Meera Iyer (meera@example.com)')).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
