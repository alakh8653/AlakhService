import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ToastProvider } from '../../components/Toast';
import UsersPage from '../UsersPage';
import { getRiskHistory, getRiskLevels } from '../RiskService';
import { banAccount, searchAccounts, unbanAccount } from '../UserService';

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

describe('UsersPage search', () => {
  it('searches as the admin types, once typing pauses', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<UsersPage />);
      await screen.findByText('Ravi');
      expect(searchAccounts).toHaveBeenLastCalledWith('', 50);
      fireEvent.change(screen.getByRole('searchbox', { name: 'Search users' }), { target: { value: 'asha' } });
      expect(searchAccounts).toHaveBeenCalledTimes(1);
      await act(async () => {
        vi.advanceTimersByTime(400);
      });
      expect(searchAccounts).toHaveBeenCalledTimes(2);
      expect(searchAccounts).toHaveBeenLastCalledWith('asha', 50);
    } finally {
      vi.useRealTimers();
    }
  });

  it('searches immediately on Enter and ignores an older, slower answer', async () => {
    let answerFirst: (v: ReturnType<typeof account>[]) => void = () => {};
    vi.mocked(searchAccounts)
      .mockImplementationOnce(() => new Promise((resolve) => (answerFirst = resolve)))
      .mockResolvedValueOnce([account('u2', 'Asha')]);
    render(<UsersPage />);
    const box = screen.getByRole('searchbox', { name: 'Search users' });
    fireEvent.change(box, { target: { value: 'asha' } });
    fireEvent.submit(box);
    expect(await screen.findByText('Asha')).toBeInTheDocument();
    await act(async () => answerFirst([account('u1', 'Ravi')]));
    expect(screen.queryByText('Ravi')).not.toBeInTheDocument();
    expect(screen.getByText('1 account matches “asha”')).toBeInTheDocument();
  });
});

describe('UsersPage ban and unban', () => {
  it('asks for a reason in a dialog before banning, then confirms', async () => {
    vi.mocked(banAccount).mockResolvedValue(undefined);
    render(
      <ToastProvider>
        <UsersPage />
      </ToastProvider>,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Ban Ravi' }));
    const dialog = screen.getByRole('dialog', { name: 'Ban Ravi?' });
    const confirm = within(dialog).getByRole('button', { name: 'Ban account' });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Reason/ }), { target: { value: 'Fake bookings' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(banAccount).toHaveBeenCalledWith('u1', 'Fake bookings');
    expect(within(screen.getByText('Ravi').closest('tr')!).getByText('Banned')).toBeInTheDocument();
    expect(screen.getByText('Ravi is banned and has been signed out.')).toBeInTheDocument();
  });

  it('cancels with Escape without changing anything', async () => {
    render(<UsersPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Ban Ravi' }));
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(banAccount).not.toHaveBeenCalled();
  });

  it('keeps the dialog open with the API message when the change fails', async () => {
    vi.mocked(searchAccounts).mockResolvedValue([{ ...account('u1', 'Ravi'), isActive: false }]);
    vi.mocked(unbanAccount).mockRejectedValue({ response: { data: { detail: 'Account not found' } } });
    render(<UsersPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Unban Ravi' }));
    fireEvent.click(screen.getByRole('button', { name: 'Restore access' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Account not found');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('does not offer to ban the signed-in admin', async () => {
    vi.mocked(searchAccounts).mockResolvedValue([account('admin-1', 'Me Admin')]);
    render(<UsersPage />);
    expect(await screen.findByText('(you)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Ban Me Admin/ })).not.toBeInTheDocument();
  });
});
