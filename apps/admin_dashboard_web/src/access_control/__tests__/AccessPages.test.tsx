import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import RolesPage from '../RolesPage';
import PermissionsPage from '../PermissionsPage';
import { deleteRole, getPermissions, getRoles, updateRolePermissions, type Role } from '../AccessControlService';
import { ToastProvider } from '../../components/Toast';

vi.mock('../AccessControlService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../AccessControlService')>()),
  getRoles: vi.fn(),
  getPermissions: vi.fn(),
  updateRolePermissions: vi.fn(),
  createRole: vi.fn(),
  deleteRole: vi.fn(),
}));

const auditor: Role = { id: 'r-aud', name: 'auditor', description: 'Reads audit logs', permissions: ['audit:read'], isSystem: false, userCount: 2 };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRoles).mockResolvedValue([auditor]);
  vi.mocked(getPermissions).mockResolvedValue([
    { key: 'audit:read', resource: 'audit', description: 'View audit logs' },
    { key: 'users:ban', resource: 'users', description: 'Ban and unban accounts' },
  ]);
});

describe('RolesPage', () => {
  it('expands a role as a disclosure and saves with feedback', async () => {
    vi.mocked(updateRolePermissions).mockResolvedValue({ ...auditor, permissions: ['audit:read', 'users:ban'] });
    render(
      <ToastProvider>
        <RolesPage />
      </ToastProvider>,
    );
    const toggle = await screen.findByRole('button', { name: /auditor/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(screen.getByRole('checkbox', { name: /users:ban/ }));
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save permissions' }));
    expect(await screen.findByText('Permissions saved for auditor.')).toBeInTheDocument();
    expect(updateRolePermissions).toHaveBeenCalledWith('r-aud', ['audit:read', 'users:ban']);
  });

  it('asks before deleting a role and says who is affected', async () => {
    vi.mocked(deleteRole).mockResolvedValue();
    render(<RolesPage />);
    fireEvent.click(await screen.findByRole('button', { name: /auditor/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete role…' }));
    const dialog = screen.getByRole('dialog', { name: 'Delete the auditor role?' });
    expect(within(dialog).getByText(/2 people have this role/)).toBeInTheDocument();
    expect(deleteRole).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete role' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: /auditor/ })).not.toBeInTheDocument());
    expect(deleteRole).toHaveBeenCalledWith('r-aud');
  });
});

describe('PermissionsPage', () => {
  it('filters by description too, with a labelled field', async () => {
    render(<PermissionsPage />);
    await screen.findByText('audit:read');
    fireEvent.change(screen.getByRole('searchbox', { name: 'Filter permissions' }), { target: { value: 'unban' } });
    expect(screen.queryByText('audit:read')).not.toBeInTheDocument();
    expect(screen.getByText('users:ban')).toBeInTheDocument();
    expect(within(screen.getByText('users:ban').closest('tr')!).getByText('No role')).toBeInTheDocument();
  });
});
