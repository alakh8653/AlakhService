import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import adminApiClient from '../../apiClient';
import ReviewReportsPage from '../ReviewReportsPage';

const toast = vi.fn();
vi.mock('../../components/Toast', () => ({ useToast: () => toast }));

const review = {
  id: 'r1',
  shop_id: 's1',
  rating: 1,
  comment: 'Very bad, call me',
  reviewer_name: 'Asha R.',
  created_at: '2026-11-04T06:00:00Z',
  is_hidden: false,
  report_count: 2,
  report_reasons: ['Abusive', 'Not a real customer'],
};

describe('ReviewReportsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    toast.mockReset();
  });

  it('shows what was reported and why, and reads the hidden ones separately', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValue({ data: { items: [review] } });
    render(<ReviewReportsPage />);
    expect(await screen.findByText('Reported by 2 people')).toBeTruthy();
    expect(screen.getByText('Abusive')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/admin/reviews/reported', { params: { hidden: false, limit: 50 } });
    fireEvent.click(screen.getByRole('button', { name: 'Hidden' }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('/admin/reviews/reported', { params: { hidden: true, limit: 50 } }));
  });

  it('keeps and hides', async () => {
    vi.spyOn(adminApiClient, 'get').mockResolvedValue({ data: { items: [review] } });
    const put = vi.spyOn(adminApiClient, 'put').mockResolvedValue({ data: {} });
    render(<ReviewReportsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Keep' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/admin/reviews/r1/visibility', { hidden: false }));
    fireEvent.click(await screen.findByRole('button', { name: 'Hide' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/admin/reviews/r1/visibility', { hidden: true }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith('Review hidden.'));
  });

  it('says so when the list is empty or cannot load', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValueOnce({ data: { items: [] } });
    const { unmount } = render(<ReviewReportsPage />);
    expect(await screen.findByText('Nothing here.')).toBeTruthy();
    unmount();
    get.mockRejectedValueOnce({ response: { data: { detail: 'No' } } });
    render(<ReviewReportsPage />);
    expect(await screen.findByRole('alert')).toBeTruthy();
  });
});
