import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import DisputeListPage from '../DisputeListPage';
import DisputeDetailPage from '../DisputeDetailPage';
import BookingPayments from '../BookingPayments';
import { getDisputeById, getDisputeMessages, getDisputes, resolveDispute, startReview, type Dispute } from '../DisputeService';
import { getBookingPayments, refundPayment } from '../PaymentService';
import { lookupAccount } from '../../users/accountNames';

vi.mock('../../apiClient', () => ({ default: {}, currentAdminId: () => 'admin-1' }));
vi.mock('../DisputeService', async (importOriginal) => {
  const real = await importOriginal<typeof import('../DisputeService')>();
  return {
    ...real,
    getDisputes: vi.fn(),
    getDisputeById: vi.fn(),
    getDisputeMessages: vi.fn(),
    startReview: vi.fn(),
    escalateDispute: vi.fn(),
    resolveDispute: vi.fn(),
    addDisputeMessage: vi.fn(),
  };
});
vi.mock('../PaymentService', () => ({ getBookingPayments: vi.fn(), refundPayment: vi.fn() }));
vi.mock('../../users/accountNames', () => ({
  lookupAccount: vi.fn(),
  useAccounts: (ids: (string | null | undefined)[]) =>
    ids.includes('cust-1') ? { 'cust-1': { id: 'cust-1', name: 'Priya Sharma', email: 'priya@example.com', phone: null } } : {},
}));

const dispute = (over: Partial<Dispute> = {}): Dispute => ({
  id: '3820d121-480b-46ab-b2a9-1c8edd7c98cd',
  caseNumber: '3820D121',
  bookingId: 'b0000000-1111-2222-3333-444444444444',
  raisedBy: 'cust-1',
  type: 'service_quality',
  description: 'Technician left early',
  status: 'OPEN',
  resolution: null,
  evidenceUrls: [],
  createdAt: '2026-10-16T06:30:00Z',
  resolvedAt: null,
  outcome: null,
  refundAmountCents: null,
  ...over,
});

function Where() {
  const l = useLocation();
  return <p data-testid="where">{l.pathname + l.search}</p>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(lookupAccount).mockResolvedValue(null);
  vi.mocked(getDisputes).mockResolvedValue({ data: [dispute()], total: 1, page: 1 });
  vi.mocked(getDisputeById).mockResolvedValue(dispute());
  vi.mocked(getDisputeMessages).mockResolvedValue([]);
  vi.mocked(getBookingPayments).mockResolvedValue([]);
});

describe('DisputeListPage', () => {
  const renderList = (path = '/disputes') =>
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/disputes" element={<><DisputeListPage /><Where /></>} />
          <Route path="/disputes/:id" element={<Where />} />
        </Routes>
      </MemoryRouter>,
    );

  it('shows who raised the case by name and dates in IST', async () => {
    renderList();
    expect(await screen.findByText('Priya Sharma')).toBeInTheDocument();
    expect(screen.getByText('16 Oct 2026')).toBeInTheDocument();
  });

  it('keeps the status filter in the URL and offers "All"', async () => {
    renderList('/disputes?status=ESCALATED');
    await screen.findByText('Priya Sharma');
    expect(getDisputes).toHaveBeenLastCalledWith({ status: 'ESCALATED', page: 1, perPage: 20 });
    expect(screen.getByRole('button', { name: 'Escalated' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'All' }));
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/disputes$/);
    await waitFor(() => expect(getDisputes).toHaveBeenLastCalledWith({ status: undefined, page: 1, perPage: 20 }));
  });

  it('opens a case from the keyboard', async () => {
    renderList();
    const row = await screen.findByRole('row', { name: /Open case 3820D121/ });
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(screen.getByTestId('where')).toHaveTextContent('/disputes/3820d121-480b-46ab-b2a9-1c8edd7c98cd');
  });

  it('explains an empty filtered list', async () => {
    vi.mocked(getDisputes).mockResolvedValue({ data: [], total: 0, page: 1 });
    renderList('/disputes?status=OPEN');
    expect(await screen.findByText('No open disputes - nothing is waiting for review.')).toBeInTheDocument();
  });
});

describe('DisputeDetailPage', () => {
  const renderDetail = () =>
    render(
      <MemoryRouter initialEntries={['/disputes/3820d121-480b-46ab-b2a9-1c8edd7c98cd']}>
        <Routes>
          <Route path="/disputes/:id" element={<DisputeDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

  it('puts the next step at the top; starting a review is one click and offers the next actions', async () => {
    vi.mocked(startReview).mockResolvedValue(dispute({ status: 'UNDER_REVIEW' }));
    renderDetail();
    expect(await screen.findByText(/Start a review to show the parties/)).toBeInTheDocument();
    expect(screen.getByText(/Priya Sharma/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Start review' }));
    expect(await screen.findByRole('button', { name: 'Resolve…' })).toBeInTheDocument();
    expect(startReview).toHaveBeenCalledWith(dispute().id);
    expect(screen.getByRole('button', { name: 'Escalate…' })).toBeInTheDocument();
  });

  it('needs resolution notes in the confirmation before resolving', async () => {
    vi.mocked(getDisputeById).mockResolvedValue(dispute({ status: 'UNDER_REVIEW' }));
    vi.mocked(resolveDispute).mockResolvedValue(dispute({ status: 'RESOLVED', resolution: 'Refunded in full', resolvedAt: '2026-10-17T06:30:00Z' }));
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: 'Resolve…' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Resolve case' });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Resolution/ }), { target: { value: 'Refunded in full' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(resolveDispute).toHaveBeenCalled());
    expect(await screen.findByText('Refunded in full')).toBeInTheDocument();
    expect(resolveDispute).toHaveBeenCalledWith(dispute().id, 'Refunded in full', 'REFUND_FULL', undefined);
    expect(screen.getByText('This case is closed.')).toBeInTheDocument();
  });

  it('chooses what happens to the money; a partial refund needs an amount', async () => {
    vi.mocked(getDisputeById).mockResolvedValue(dispute({ status: 'UNDER_REVIEW' }));
    vi.mocked(resolveDispute).mockResolvedValue(
      dispute({ status: 'RESOLVED', resolution: 'Half done', outcome: 'REFUND_PARTIAL', refundAmountCents: 25000 }),
    );
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: 'Resolve…' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('radio', { name: /Full refund to the customer/ })).toBeChecked();
    fireEvent.click(within(dialog).getByRole('radio', { name: /Partial refund/ }));
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Resolution/ }), { target: { value: 'Half done' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve case' }));
    expect(await within(dialog).findByText('Enter the amount to refund, in rupees.')).toBeInTheDocument();
    expect(resolveDispute).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText('Amount to refund (₹)'), { target: { value: '250' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve case' }));
    await waitFor(() => expect(resolveDispute).toHaveBeenCalledWith(dispute().id, 'Half done', 'REFUND_PARTIAL', 25000));
    expect(await screen.findByText(/Partial refund to the customer \(₹250.00\)/)).toBeInTheDocument();
  });

  it('releases the money to the shop', async () => {
    vi.mocked(getDisputeById).mockResolvedValue(dispute({ status: 'ESCALATED' }));
    vi.mocked(resolveDispute).mockResolvedValue(dispute({ status: 'RESOLVED', resolution: 'Shop did the work', outcome: 'RELEASE_TO_SHOP' }));
    renderDetail();
    fireEvent.click(await screen.findByRole('button', { name: 'Resolve…' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('radio', { name: /Release the money to the shop/ }));
    fireEvent.change(within(dialog).getByRole('textbox', { name: /Resolution/ }), { target: { value: 'Shop did the work' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resolve case' }));
    await waitFor(() => expect(resolveDispute).toHaveBeenCalledWith(dispute().id, 'Shop did the work', 'RELEASE_TO_SHOP', undefined));
  });

  it('offers a retry and a way back when the case cannot be loaded', async () => {
    vi.mocked(getDisputeById).mockRejectedValueOnce(new Error('down'));
    renderDetail();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this dispute.');
    expect(screen.getByRole('link', { name: 'Back to disputes' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Case #3820D121' })).toBeInTheDocument();
  });
});

describe('BookingPayments', () => {
  it('shows amounts with Indian grouping and refunds only after confirming with a reason', async () => {
    vi.mocked(getBookingPayments).mockResolvedValue([
      { id: 'p1', amountCents: 12345600, method: 'upi', gateway: 'razorpay', status: 'COMPLETED', createdAt: '2026-10-16T06:30:00Z' },
    ]);
    vi.mocked(refundPayment).mockResolvedValue({ id: 'r1', amountCents: 50000, status: 'PROCESSED' });
    render(<BookingPayments bookingId="b1" />);
    expect(await screen.findByText('₹1,23,456.00')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Refund amount (₹)'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refund…' }));
    const dialog = screen.getByRole('dialog', { name: 'Refund ₹500.00?' });
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'Late arrival' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Refund ₹500.00' }));
    await waitFor(() => expect(refundPayment).toHaveBeenCalledWith('p1', 50000, 'Late arrival'));
  });
});
