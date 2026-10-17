import { fireEvent, render, screen, within } from '@testing-library/react';
import UsersPage from '../UsersPage';
import { getRiskHistory, getRiskLevels } from '../RiskService';
import { searchAccounts } from '../UserService';

vi.mock('../../apiClient', () => ({ default: {}, currentAdminId: () => 'admin-1' }));
vi.mock('../UserService', () => ({ searchAccounts: vi.fn(), banAccount: vi.fn(), unbanAccount: vi.fn() }));
vi.mock('../RiskService', () => ({ getRiskLevels: vi.fn(), getRiskHistory: vi.fn() }));

const account = (id: string, name: string) => ({
  id,
  name,
  email: `${id}@example.com`,
  phone: null,
  role: 'user',
  isActive: true,
  isVerified: true,
  createdAt: '2026-10-01T00:00:00Z',
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(searchAccounts).mockResolvedValue([account('u1', 'Ravi'), account('u2', 'Asha')]);
  vi.mocked(getRiskLevels).mockResolvedValue({
    u1: { userId: 'u1', score: 0.62, level: 'HIGH', riskEvents: 3, safeEvents: 1, lastUpdated: '2026-10-02T00:00:00Z' },
  });
  vi.mocked(getRiskHistory).mockResolvedValue([
    { id: 's1', type: 'late_cancellation', value: 0.4, createdAt: '2026-10-02T10:00:00Z' },
  ]);
});

describe('UsersPage risk column', () => {
  it('shows each listed user’s risk level from one lookup, and a dash without a profile', async () => {
    render(<UsersPage />);
    const ravi = (await screen.findByText('Ravi')).closest('tr')!;
    expect(await within(ravi).findByText('High')).toBeInTheDocument();
    expect(within(screen.getByText('Asha').closest('tr')!).getAllByText('—').length).toBeGreaterThan(0);
    expect(getRiskLevels).toHaveBeenCalledTimes(1);
    expect(getRiskLevels).toHaveBeenCalledWith(['u1', 'u2']);
  });

  it('opens the user’s recent signals when the badge is clicked', async () => {
    render(<UsersPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Risk signals for Ravi' }));
    const panel = await screen.findByRole('region', { name: 'Risk signals for Ravi' });
    expect(await within(panel).findByText('late cancellation')).toBeInTheDocument();
    expect(getRiskHistory).toHaveBeenCalledWith('u1');

    fireEvent.click(within(panel).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('region', { name: 'Risk signals for Ravi' })).not.toBeInTheDocument();
  });

  it('still lists the users when risk levels cannot be loaded', async () => {
    vi.mocked(getRiskLevels).mockRejectedValue(new Error('down'));
    render(<UsersPage />);
    expect(await screen.findByText('Risk levels could not be loaded.')).toBeInTheDocument();
    expect(screen.getByText('Ravi')).toBeInTheDocument();
  });
});
