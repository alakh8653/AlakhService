import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ToastProvider } from '../../components/Toast';
import ShopsPage from '../ShopsPage';
import * as service from '../ShopReviewService';

const shop: service.ShopForReview = {
  id: 'shop-1',
  ownerId: 'o1',
  name: 'Glow Salon',
  category: 'salon',
  city: 'Pune',
  address: '12 MG Road',
  phone: '+919876543210',
  email: null,
  isActive: true,
  status: 'PENDING_REVIEW',
  rejectionReason: null,
  legalName: 'Glow Salon Pvt Ltd',
  legalAddress: null,
  gstin: '27AAPFU0939F1ZV',
  createdAt: '2026-10-20T09:00:00Z',
  submittedAt: '2026-10-21T09:00:00Z',
  reviewedAt: null,
  hasPayoutDetails: false,
  documents: [
    { id: 'd1', type: 'PAN', url: '/api/v1/shops/shop-1/documents/d1/file', uploaded: true, fileName: 'pan.pdf', contentType: 'application/pdf', sizeBytes: 2048, isVerified: false, createdAt: null },
    { id: 'd2', type: 'GST', url: 'https://drive.example.com/gst', uploaded: false, fileName: null, contentType: null, sizeBytes: null, isVerified: false, createdAt: null },
  ],
};

const renderPage = () =>
  render(
    <ToastProvider>
      <ShopsPage />
    </ToastProvider>,
  );

describe('ShopsPage', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('shows the review queue with KYC details and documents', async () => {
    vi.spyOn(service, 'getReviewQueue').mockResolvedValue([shop]);
    renderPage();
    const card = await screen.findByRole('article', { name: 'Glow Salon' });
    expect(within(card).getByText('Glow Salon Pvt Ltd')).toBeInTheDocument();
    expect(within(card).getByText('27AAPFU0939F1ZV')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'View PAN card (pan.pdf)' })).toBeInTheDocument();
    const link = within(card).getByRole('link', { name: 'Open GST certificate (external link)' });
    expect(link).toHaveAttribute('href', 'https://drive.example.com/gst');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('approves a shop and removes it from the queue', async () => {
    vi.spyOn(service, 'getReviewQueue').mockResolvedValue([shop]);
    const approve = vi.spyOn(service, 'approveShop').mockResolvedValue({ ...shop, status: 'APPROVED' });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /Approve/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve shop' }));
    await waitFor(() => expect(approve).toHaveBeenCalledWith('shop-1'));
    expect(await screen.findByText('No shops are waiting for review.')).toBeInTheDocument();
  });

  it('needs a reason to reject', async () => {
    vi.spyOn(service, 'getReviewQueue').mockResolvedValue([shop]);
    const reject = vi.spyOn(service, 'rejectShop').mockResolvedValue({ ...shop, status: 'REJECTED' });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /Reject/ }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Reject shop' });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole('textbox'), { target: { value: 'PAN photo is blurred' } });
    fireEvent.click(confirm);
    await waitFor(() => expect(reject).toHaveBeenCalledWith('shop-1', 'PAN photo is blurred'));
  });

  it('shows an error when the queue cannot load', async () => {
    vi.spyOn(service, 'getReviewQueue').mockRejectedValue({ response: { status: 404, data: { detail: 'Not found' } } });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Not found');
  });

  it('lists all shops filtered by status and opens one for review', async () => {
    vi.spyOn(service, 'getReviewQueue').mockResolvedValue([]);
    const list = vi.spyOn(service, 'listShops').mockResolvedValue({ data: [shop], total: 1 });
    vi.spyOn(service, 'getShopForReview').mockResolvedValue(shop);
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'All shops' }));
    const table = await screen.findByRole('table', { name: 'Shops' });
    expect(await within(table).findByText('Glow Salon')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rejected' }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith({ status: 'REJECTED', q: '', page: 1, perPage: 25 }));
    fireEvent.click(within(table).getByRole('row', { name: 'Review Glow Salon' }));
    expect(await screen.findByRole('dialog', { name: 'Shop review' })).toBeInTheDocument();
  });
});
