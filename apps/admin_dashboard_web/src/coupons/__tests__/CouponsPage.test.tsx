import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import CouponsPage from '../CouponsPage';
import { createCoupon, getCoupons, type Coupon } from '../CouponService';
import { ToastProvider } from '../../components/Toast';

vi.mock('../CouponService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../CouponService')>()),
  getCoupons: vi.fn(),
  createCoupon: vi.fn(),
}));

const coupon = (over: Partial<Coupon> = {}): Coupon => ({
  id: 'c1',
  code: 'WELCOME10',
  discountPct: 10,
  maxUses: null,
  usesCount: 1234,
  validFrom: null,
  validTo: null,
  isActive: true,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getCoupons).mockResolvedValue([coupon(), coupon({ id: 'c2', code: 'OLD5', validTo: '2020-01-01T00:00:00Z' })]);
});

describe('CouponsPage', () => {
  it('shows expired coupons as expired, not active', async () => {
    render(<CouponsPage />);
    const old = (await screen.findByText('OLD5')).closest('tr')!;
    expect(within(old).getByText('Expired')).toBeInTheDocument();
    expect(within(old).getByText('1,234 (no limit)')).toBeInTheDocument();
  });

  it('summarises the coupon and only creates it after confirmation', async () => {
    vi.mocked(createCoupon).mockResolvedValue(coupon({ id: 'c3', code: 'DIWALI25', discountPct: 25, usesCount: 0, maxUses: 100 }));
    render(
      <ToastProvider>
        <CouponsPage />
      </ToastProvider>,
    );
    await screen.findByText('WELCOME10');
    fireEvent.change(screen.getByLabelText(/^Code/), { target: { value: 'diwali25' } });
    fireEvent.change(screen.getByLabelText(/^Discount %/), { target: { value: '25' } });
    fireEvent.change(screen.getByLabelText(/^Max uses/), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create coupon…' }));

    const dialog = screen.getByRole('dialog', { name: 'Create DIWALI25?' });
    expect(within(dialog).getByText('25% off')).toBeInTheDocument();
    expect(within(dialog).getByText(/Up to 100 uses in total/)).toBeInTheDocument();
    expect(createCoupon).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create and publish' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(createCoupon).toHaveBeenCalledWith({ code: 'DIWALI25', discountPct: 25, maxUses: 100, validTo: null });
    expect(screen.getByText('DIWALI25 is live - customers can use it now.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Code/)).toHaveValue('');
  });

  it('flags a duplicate code or an out-of-range discount before submitting', async () => {
    render(<CouponsPage />);
    await screen.findByText('WELCOME10');
    fireEvent.change(screen.getByLabelText(/^Code/), { target: { value: 'welcome10' } });
    expect(screen.getByText('This code already exists.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create coupon…' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/^Code/), { target: { value: 'NEW1' } });
    fireEvent.change(screen.getByLabelText(/^Discount %/), { target: { value: '80' } });
    expect(screen.getByLabelText(/^Discount %/)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('button', { name: 'Create coupon…' })).toBeDisabled();
  });
});
