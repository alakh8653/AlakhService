import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import BookingCard from '../BookingCard';
import * as bookings from '../../services/bookingService';
import type { Booking } from '../../types';

vi.mock('../../services/bookingService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/bookingService')>()),
  getExtraCharges: vi.fn(),
  askExtraCharge: vi.fn(),
  withdrawExtraCharge: vi.fn(),
}));
vi.mock('../../services/paymentService', () => ({ getBookingPayments: vi.fn().mockResolvedValue([]), confirmCashReceived: vi.fn() }));

const api = vi.mocked(bookings);

const visit: Booking = {
  id: 'b1',
  bookingNumber: 'BK-1',
  customerId: 'c1',
  customerDisplayName: 'Ravi S.',
  providerId: 'p1',
  serviceId: 'svc1',
  shopId: 's1',
  status: 'PROVIDER_EN_ROUTE',
  scheduledAt: '2026-10-10T10:00:00Z',
  durationMinutes: 45,
  serviceMode: 'AT_HOME',
  itemDescription: null,
  readyBy: null,
  addressId: null,
  notes: null,
  totalAmount: 49900,
  createdAt: '',
  updatedAt: '',
};

describe('BookingCard start code', () => {
  beforeEach(() => vi.clearAllMocks());

  it('starts a home visit only with the code, and shows why a code was refused', async () => {
    const onChangeStatus = vi.fn();
    const onStart = vi
      .fn()
      .mockResolvedValueOnce('Ask the customer for the 4-digit start code')
      .mockResolvedValueOnce('Too many wrong codes. Wait 15 minutes, then try again.')
      .mockResolvedValueOnce(null);
    render(<BookingCard booking={visit} onChangeStatus={onChangeStatus} onStart={onStart} onCancel={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Start service' }));
    const dialog = screen.getByRole('dialog', { name: 'Start booking #BK-1' });
    expect(dialog).toHaveTextContent('Ask the customer for their 4-digit start code');

    // No code, no start.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start job' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Enter the 4-digit code');
    expect(onStart).not.toHaveBeenCalled();

    const input = within(dialog).getByLabelText('Start code');
    fireEvent.change(input, { target: { value: '12a3' } });
    expect(input).toHaveValue('123');
    fireEvent.change(input, { target: { value: '1111' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start job' }));
    await waitFor(() => expect(within(dialog).getByRole('alert')).toHaveTextContent('Ask the customer for the 4-digit start code'));
    expect(onStart).toHaveBeenCalledWith('b1', 'IN_PROGRESS', '1111');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Start job' }));
    await waitFor(() => expect(within(dialog).getByRole('alert')).toHaveTextContent('Too many wrong codes'));

    fireEvent.change(input, { target: { value: '4821' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start job' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onStart).toHaveBeenLastCalledWith('b1', 'IN_PROGRESS', '4821');
    // The plain status change never ran without the code.
    expect(onChangeStatus).not.toHaveBeenCalled();
  });

  it('asks for it when collecting a pickup, not for the steps around it', () => {
    const onChangeStatus = vi.fn();
    render(
      <BookingCard booking={{ ...visit, status: 'ASSIGNED', serviceMode: 'PICKUP_DROP' }} onChangeStatus={onChangeStatus} onStart={vi.fn()} onCancel={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Item picked up' }));
    const dialog = screen.getByRole('dialog', { name: 'Start booking #BK-1' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Not now' }));
    expect(onChangeStatus).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'On the way to collect' }));
    expect(onChangeStatus).toHaveBeenCalledWith('b1', 'PROVIDER_EN_ROUTE');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('does not ask at the shop', () => {
    const onChangeStatus = vi.fn();
    render(<BookingCard booking={{ ...visit, serviceMode: 'AT_SHOP', status: 'CONFIRMED' }} onChangeStatus={onChangeStatus} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Customer arrived' }));
    expect(onChangeStatus).toHaveBeenCalledWith('b1', 'IN_PROGRESS');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('BookingCard extra charges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getExtraCharges.mockResolvedValue([
      { id: 'x0', bookingId: 'b1', amountCents: 20000, reason: 'Wiring', status: 'DECLINED', createdAt: '', decidedAt: '' },
    ]);
  });

  it('asks the customer to approve an extra charge, and says it is waiting', async () => {
    const onUpdated = vi.fn();
    api.askExtraCharge.mockImplementation(async (_id, amountCents, reason) => ({
      ...visit,
      status: 'IN_PROGRESS',
      pendingExtraId: 'x1',
      pendingExtraAmount: amountCents,
      pendingExtraReason: reason,
    }));
    render(<BookingCard booking={{ ...visit, status: 'IN_PROGRESS' }} onChangeStatus={vi.fn()} onCancel={vi.fn()} onUpdated={onUpdated} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add extra charge' }));
    const dialog = screen.getByRole('dialog', { name: 'Extra charge for #BK-1' });
    expect(dialog).toHaveTextContent('The customer must approve this');
    expect(await within(dialog).findByText('₹200 for Wiring · Declined by the customer')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Send to customer' }));
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Say what the extra charge is for');
    expect(api.askExtraCharge).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText('What is it for?'), { target: { value: 'New capacitor' } });
    fireEvent.change(within(dialog).getByLabelText('Amount (₹)'), { target: { value: '350.50' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send to customer' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.askExtraCharge).toHaveBeenCalledWith('b1', 35050, 'New capacitor');
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ pendingExtraId: 'x1' }));
    expect(screen.getByTestId('extras-line')).toHaveTextContent('Extra ₹350.50 for New capacitor: waiting for the customer to approve');
    expect(screen.getByRole('button', { name: 'Add extra charge' })).toBeDisabled();
  });

  it('shows the server refusing (409) and keeps the form', async () => {
    api.askExtraCharge.mockRejectedValue(
      Object.assign(new Error('409'), {
        response: { status: 409, data: { detail: 'This booking is already paid, so an extra charge cannot be added in the app yet' } },
      }),
    );
    render(<BookingCard booking={{ ...visit, status: 'IN_PROGRESS' }} onChangeStatus={vi.fn()} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add extra charge' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('What is it for?'), { target: { value: 'New capacitor' } });
    fireEvent.change(within(dialog).getByLabelText('Amount (₹)'), { target: { value: '350' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send to customer' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('already paid');
  });

  it('takes back a request the customer has not answered', async () => {
    api.withdrawExtraCharge.mockResolvedValue({ ...visit, status: 'IN_PROGRESS', pendingExtraId: null, updatedAt: 'z' });
    render(
      <BookingCard
        booking={{ ...visit, status: 'IN_PROGRESS', pendingExtraId: 'x1', pendingExtraAmount: 5000, pendingExtraReason: 'Wiring' }}
        onChangeStatus={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Take back' }));
    await waitFor(() => expect(screen.queryByTestId('extras-line')).not.toBeInTheDocument());
    expect(api.withdrawExtraCharge).toHaveBeenCalledWith('b1', 'x1');
  });

  it('shows approved extras and the free-fix label, and offers no extras once done', () => {
    const { rerender } = render(
      <BookingCard booking={{ ...visit, status: 'IN_PROGRESS', extraAmount: 25000 }} onChangeStatus={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByTestId('extras-line')).toHaveTextContent('Customer approved ₹250 extra');
    expect(screen.queryByText('Free fix')).not.toBeInTheDocument();
    rerender(<BookingCard booking={{ ...visit, status: 'COMPLETED', reworkOf: 'b0', totalAmount: 0 }} onChangeStatus={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText('Free fix')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add extra charge' })).not.toBeInTheDocument();
  });
});
