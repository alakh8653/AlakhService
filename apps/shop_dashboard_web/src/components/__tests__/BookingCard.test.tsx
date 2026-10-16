import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import BookingCard from '../BookingCard';
import type { Booking } from '../../types';

const booking: Booking = {
  id: 'b1',
  bookingNumber: 'BK-1',
  customerId: 'abcdef123456',
  providerId: null,
  serviceId: 'svc1',
  shopId: 's1',
  status: 'PENDING',
  scheduledAt: '2026-10-10T10:00:00Z',
  durationMinutes: 45,
  serviceMode: 'AT_SHOP',
  itemDescription: null,
  readyBy: null,
  addressId: null,
  notes: null,
  totalAmount: 49900,
  createdAt: '',
  updatedAt: '',
};

describe('BookingCard', () => {
  it('offers confirm and cancel on a pending booking', () => {
    const onChangeStatus = vi.fn();
    const onCancel = vi.fn();
    vi.spyOn(window, 'prompt').mockReturnValue('Closed today');
    render(<BookingCard booking={booking} serviceName="Haircut" onChangeStatus={onChangeStatus} onCancel={onCancel} />);

    expect(screen.getByText('₹499.00')).toBeInTheDocument();
    expect(screen.getByText(/Haircut/)).toBeInTheDocument();
    expect(screen.getByText('Customer ABCDEF12')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(onChangeStatus).toHaveBeenCalledWith('b1', 'CONFIRMED');

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledWith('b1', 'Closed today');
  });

  it('offers no actions once a booking is completed', () => {
    render(<BookingCard booking={{ ...booking, status: 'COMPLETED' }} onChangeStatus={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });
});

describe('BookingCard assignment', () => {
  const providers = [
    { userId: 'u-ravi', name: 'Ravi' },
    { userId: 'u-meena', name: 'Meena' },
  ];

  it('assigns a confirmed booking to a chosen staff member', () => {
    const onAssign = vi.fn();
    render(
      <BookingCard booking={{ ...booking, status: 'CONFIRMED' }} providers={providers} onChangeStatus={vi.fn()} onCancel={vi.fn()} onAssign={onAssign} />,
    );
    fireEvent.change(screen.getByLabelText('Assign to'), { target: { value: 'u-meena' } });
    expect(onAssign).toHaveBeenCalledWith('b1', 'u-meena');
  });

  it('names the assigned provider and offers no picker once assigned', () => {
    render(
      <BookingCard booking={{ ...booking, status: 'ASSIGNED', providerId: 'u-ravi' }} providers={providers} onChangeStatus={vi.fn()} onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    expect(screen.getByText('Provider: Ravi')).toBeInTheDocument();
    expect(screen.queryByLabelText('Assign to')).not.toBeInTheDocument();
  });
});

describe('BookingCard delivery modes', () => {
  it('shows a pickup job with its item and only the pickup steps', () => {
    const onChangeStatus = vi.fn();
    const job: Booking = {
      ...booking,
      status: 'IN_PROGRESS',
      serviceMode: 'PICKUP_DROP',
      itemDescription: 'Dell XPS 13, cracked screen',
      addressId: 'addr-12345678',
    };
    render(<BookingCard booking={job} serviceName="Laptop repair" onChangeStatus={onChangeStatus} onCancel={vi.fn()} />);
    expect(screen.getByText('Pickup & drop')).toBeInTheDocument();
    expect(screen.getByText('Dell XPS 13, cracked screen')).toBeInTheDocument();
    expect(screen.getByText(/saved address ADDR-123/)).toBeInTheDocument();
    // Repaired items go back to the customer before the job is complete.
    expect(screen.queryByRole('button', { name: 'Mark complete' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Send it back' }));
    expect(onChangeStatus).toHaveBeenCalledWith('b1', 'OUT_FOR_DELIVERY');
  });

  it('starts an at-shop booking when the customer arrives', () => {
    const onChangeStatus = vi.fn();
    render(<BookingCard booking={{ ...booking, status: 'CONFIRMED' }} onChangeStatus={onChangeStatus} onCancel={vi.fn()} />);
    expect(screen.getByText('At the shop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Customer arrived' }));
    expect(onChangeStatus).toHaveBeenCalledWith('b1', 'IN_PROGRESS');
  });
});

describe('BookingCard return time', () => {
  const pickup: Booking = { ...booking, serviceMode: 'PICKUP_DROP', status: 'PICKED_UP', itemDescription: 'Dell XPS 13' };

  it('tells the customer when their item will be back', () => {
    const onSetReadyBy = vi.fn();
    render(<BookingCard booking={pickup} onChangeStatus={vi.fn()} onCancel={vi.fn()} onSetReadyBy={onSetReadyBy} />);
    expect(screen.getByText('No return time given yet')).toBeInTheDocument();

    const save = screen.getByRole('button', { name: 'Tell customer' });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Expected back by'), { target: { value: '2026-10-12T17:00' } });
    fireEvent.click(save);
    // The input is in the browser's local time; the API gets the same moment as ISO.
    expect(onSetReadyBy).toHaveBeenCalledWith('b1', new Date('2026-10-12T17:00').toISOString());
  });

  it('shows, changes and clears a promised time', () => {
    const onSetReadyBy = vi.fn();
    const readyBy = new Date('2026-10-12T17:00').toISOString();
    render(<BookingCard booking={{ ...pickup, readyBy }} onChangeStatus={vi.fn()} onCancel={vi.fn()} onSetReadyBy={onSetReadyBy} />);
    expect(screen.getByText('Expected back by Oct 12, 5:00 PM')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Update' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onSetReadyBy).toHaveBeenCalledWith('b1', null);
  });

  it('only shows the promise once the item is on its way back, and never for other modes', () => {
    const readyBy = new Date('2026-10-12T17:00').toISOString();
    const { unmount } = render(
      <BookingCard booking={{ ...pickup, status: 'OUT_FOR_DELIVERY', readyBy }} onChangeStatus={vi.fn()} onCancel={vi.fn()} onSetReadyBy={vi.fn()} />,
    );
    expect(screen.getByText('Expected back by Oct 12, 5:00 PM')).toBeInTheDocument();
    expect(screen.queryByLabelText('Expected back by')).not.toBeInTheDocument();
    unmount();

    render(<BookingCard booking={{ ...booking, status: 'CONFIRMED' }} onChangeStatus={vi.fn()} onCancel={vi.fn()} onSetReadyBy={vi.fn()} />);
    expect(screen.queryByLabelText('Expected back by')).not.toBeInTheDocument();
    expect(screen.queryByText(/return time/)).not.toBeInTheDocument();
  });
});
