import { beforeEach, describe, expect, it, vi } from 'vitest';
// The store first: it loads the services that the mocks below wrap.
import { store } from '../../state/store';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import ServicesPage from '../ServicesPage';
import StaffPage from '../StaffPage';
import QueuesPage from '../QueuesPage';
import { ToastProvider } from '../../components/Toast';
import { setCredentials } from '../../state/authSlice';
import type { Service, Shop, StaffMember } from '../../types';

const api = vi.hoisted(() => ({
  getServices: vi.fn(),
  createService: vi.fn(),
  updateService: vi.fn(),
  getStaff: vi.fn(),
  createStaffMember: vi.fn(),
  updateStaffMember: vi.fn(),
  getQueues: vi.fn(),
  getWaiting: vi.fn(),
  callNext: vi.fn(),
}));
vi.mock('../../services/shopService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/shopService')>()),
  getServices: api.getServices,
  createService: api.createService,
  updateService: api.updateService,
  getStaff: api.getStaff,
  createStaffMember: api.createStaffMember,
  updateStaffMember: api.updateStaffMember,
}));
vi.mock('../../services/queueService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/queueService')>()),
  getQueues: api.getQueues,
  getWaiting: api.getWaiting,
  callNext: api.callNext,
}));

const shop = { id: 's1', name: 'Asha Salon', isVerified: true } as Shop;
const haircut: Service = {
  id: 'svc1', shopId: 's1', categoryId: null, name: 'Haircut', description: null, priceCents: 30000, durationMinutes: 30,
  isActive: true, createdAt: '', serviceModes: ['AT_SHOP', 'AT_HOME'], homeVisitFeeCents: 10000, pickupFeeCents: 0,
};
const ravi: StaffMember = {
  id: 'st1', shopId: 's1', userId: null, name: 'Ravi', email: null, phone: '9876543210', role: 'stylist', serviceIds: [],
  isActive: true, createdAt: '',
};

const renderPage = (page: React.ReactNode) =>
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ToastProvider>{page}</ToastProvider>
      </MemoryRouter>
    </Provider>,
  );

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  api.getServices.mockResolvedValue([haircut]);
  api.getStaff.mockResolvedValue([ravi]);
  store.dispatch(setCredentials({ tokens: { accessToken: 'a', refreshToken: 'r', expiresAt: 0 }, user: { id: 'u', name: 'A', email: null, phone: null, role: 'shop_owner' }, shop }));
});

describe('ServicesPage', () => {
  it('shows prices with mode fees and hides a service with a named switch', async () => {
    api.updateService.mockResolvedValue({ ...haircut, isActive: false });
    renderPage(<ServicesPage />);
    expect(await screen.findByText(/₹300 · home visit \+₹100/)).toBeInTheDocument();
    const toggle = screen.getByRole('switch', { name: 'Haircut available to book' });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(toggle);
    expect(await screen.findByText('Haircut is hidden from customers.')).toBeInTheDocument();
    expect(api.updateService).toHaveBeenCalledWith('svc1', { isActive: false });
    expect(screen.getByRole('switch', { name: 'Haircut available to book' })).toHaveAttribute('aria-checked', 'false');
  });

  it('points out each problem in the form next to its field', async () => {
    renderPage(<ServicesPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Add service' }));
    const dialog = screen.getByRole('dialog', { name: 'New service' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add service' }));
    expect(within(dialog).getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true');
    expect(within(dialog).getByText('Enter a price above ₹0')).toBeInTheDocument();
    expect(api.createService).not.toHaveBeenCalled();
  });

  it('edits a service in a dialog and confirms the save', async () => {
    api.updateService.mockResolvedValue({ ...haircut, priceCents: 35000 });
    renderPage(<ServicesPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Haircut' }));
    const dialog = screen.getByRole('dialog', { name: 'Edit Haircut' });
    fireEvent.change(within(dialog).getByLabelText('Price (₹)'), { target: { value: '350' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Haircut saved.')).toBeInTheDocument();
    expect(api.updateService.mock.calls[0][1]).toMatchObject({ priceCents: 35000, homeVisitFeeCents: 10000 });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('StaffPage', () => {
  it('edits a staff member and links their app account', async () => {
    api.updateStaffMember.mockResolvedValue({ ...ravi, userId: 'user-ravi' });
    renderPage(<StaffPage />);
    expect(await screen.findByText('No staff app account linked')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Edit Ravi' }));
    const dialog = screen.getByRole('dialog', { name: 'Edit Ravi' });
    expect(within(dialog).getByLabelText('Mobile')).toHaveValue('9876543210');
    fireEvent.change(within(dialog).getByLabelText('Staff app account ID (optional)'), { target: { value: 'user-ravi' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Ravi saved.')).toBeInTheDocument();
    expect(api.updateStaffMember).toHaveBeenCalledWith('st1', expect.objectContaining({ userId: 'user-ravi', name: 'Ravi' }));
    expect(screen.getByText('Can take bookings')).toBeInTheDocument();
  });

  it('checks the mobile number before saving', async () => {
    renderPage(<StaffPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Add staff' }));
    const dialog = screen.getByRole('dialog', { name: 'Add a staff member' });
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Meena' } });
    fireEvent.change(within(dialog).getByLabelText('Mobile'), { target: { value: '12' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add staff member' }));
    expect(within(dialog).getByText('10-digit mobile, e.g. 98765 43210')).toBeInTheDocument();
    expect(api.createStaffMember).not.toHaveBeenCalled();
  });
});

describe('QueuesPage', () => {
  it('shows how long ago someone was called in hours, and confirms calling the next customer', async () => {
    const calledAt = new Date(Date.now() - 1575 * 60_000).toISOString();
    api.getQueues.mockResolvedValue([{ id: 'q1', serviceId: 'svc1', servers: 1, avgServiceMinutes: 30, isAccepting: true, waiting: 1 }]);
    api.getWaiting.mockResolvedValue([
      { id: 'e1', customerId: 'cust1111', status: 'CALLED', position: 0, enteredAt: calledAt, calledAt, estimatedWaitMinutes: null },
      { id: 'e2', customerId: 'cust2222', status: 'WAITING', position: 1, enteredAt: calledAt, calledAt: null, estimatedWaitMinutes: 10 },
    ]);
    api.callNext.mockResolvedValue({ id: 'e2', customerId: 'cust2222' });
    renderPage(<QueuesPage />);
    expect(await screen.findByText(/\(1 day 2 h ago\)/)).toBeInTheDocument();
    expect(screen.queryByText('Add a service first; queues are opened per service.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Call next' }));
    expect(await screen.findByText('Called customer CUST2222. They have been notified.')).toBeInTheDocument();
    await waitFor(() => expect(api.getWaiting).toHaveBeenCalledTimes(2));
  });
});
