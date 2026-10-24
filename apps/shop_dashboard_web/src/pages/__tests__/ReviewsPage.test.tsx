import { beforeEach, describe, expect, it, vi } from 'vitest';
// The store first: it loads the services that the mocks below wrap.
import { store } from '../../state/store';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import ReviewsPage from '../ReviewsPage';
import { ToastProvider } from '../../components/Toast';
import { setCredentials } from '../../state/authSlice';
import type { Review } from '../../services/reviewService';
import type { Shop } from '../../types';

const api = vi.hoisted(() => ({
  getReviewSummary: vi.fn(),
  getReviews: vi.fn(),
  replyToReview: vi.fn(),
  getServices: vi.fn(),
}));
vi.mock('../../services/reviewService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reviewService')>()),
  getReviewSummary: api.getReviewSummary,
  getReviews: api.getReviews,
  replyToReview: api.replyToReview,
}));
vi.mock('../../services/shopService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/shopService')>()),
  getServices: api.getServices,
}));

const shop = { id: 's1', name: 'Asha Salon', isVerified: true } as Shop;
const review = (id: string, over: Partial<Review> = {}): Review => ({
  id, shopId: 's1', serviceId: 'svc1', rating: 5, comment: 'Lovely haircut', reviewerName: 'Priya S.',
  createdAt: '2026-10-12T09:30:00Z', reply: null, ...over,
});
const summary = {
  averageRating: 4.3,
  reviewCount: 3,
  distribution: [
    { stars: 5, count: 2 }, { stars: 4, count: 0 }, { stars: 3, count: 1 }, { stars: 2, count: 0 }, { stars: 1, count: 0 },
  ],
};

const renderPage = () =>
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ToastProvider>
          <ReviewsPage />
        </ToastProvider>
      </MemoryRouter>
    </Provider>,
  );

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  api.getServices.mockResolvedValue([{ id: 'svc1', name: 'Haircut' }]);
  api.getReviewSummary.mockResolvedValue(summary);
  store.dispatch(setCredentials({ tokens: { accessToken: 'a', refreshToken: 'r', expiresAt: 0 }, user: { id: 'u', name: 'Asha', email: null, phone: null, role: 'shop_owner' }, shop }));
});

describe('ReviewsPage', () => {
  it('shows the summary with its distribution and the newest reviews with replies', async () => {
    api.getReviews.mockResolvedValue({
      items: [
        review('r1'),
        review('r2', { rating: 3, comment: null, reviewerName: 'Rahul', reply: { text: 'Thanks Rahul!', createdAt: '2026-10-13T10:00:00Z', updatedAt: '2026-10-14T10:00:00Z' } }),
      ],
      total: 3,
    });
    renderPage();

    expect(await screen.findByText('4.3')).toBeInTheDocument();
    expect(screen.getByText('3 reviews')).toBeInTheDocument();
    expect(screen.getByText('5 stars: 2')).toBeInTheDocument();
    expect(screen.getByText('3 stars: 1')).toBeInTheDocument();

    const first = await screen.findByRole('article', { name: 'Review by Priya S.' });
    expect(within(first).getByRole('img', { name: '5 out of 5 stars' })).toBeInTheDocument();
    expect(within(first).getByText('12 Oct 2026')).toBeInTheDocument();
    expect(within(first).getByText('Haircut')).toBeInTheDocument();
    const second = screen.getByRole('article', { name: 'Review by Rahul' });
    expect(within(second).getByText('Thanks Rahul!')).toBeInTheDocument();
    expect(within(second).getByText(/Your reply · 14 Oct 2026/)).toBeInTheDocument();
    expect(within(second).getByText('Rated without a written review.')).toBeInTheDocument();
    expect(screen.getByText('Showing 2 of 3')).toBeInTheDocument();

    api.getReviews.mockResolvedValueOnce({ items: [review('r3', { reviewerName: 'Meera K.' })], total: 3 });
    fireEvent.click(screen.getByRole('button', { name: 'Show more reviews' }));
    expect(await screen.findByRole('article', { name: 'Review by Meera K.' })).toBeInTheDocument();
    expect(api.getReviews).toHaveBeenLastCalledWith('s1', { rating: null, needsReply: false, skip: 2, limit: 10 });
    expect(screen.queryByRole('button', { name: 'Show more reviews' })).not.toBeInTheDocument();
  });

  it('filters by rating and by reviews that need a reply', async () => {
    api.getReviews.mockResolvedValue({ items: [review('r1')], total: 1 });
    renderPage();
    await screen.findByRole('article', { name: 'Review by Priya S.' });

    fireEvent.click(screen.getByRole('button', { name: '3 stars' }));
    await waitFor(() => expect(api.getReviews).toHaveBeenLastCalledWith('s1', { rating: 3, needsReply: false, limit: 10 }));
    expect(screen.getByRole('button', { name: '3 stars' })).toHaveAttribute('aria-pressed', 'true');

    api.getReviews.mockResolvedValue({ items: [], total: 0 });
    fireEvent.click(screen.getByRole('button', { name: 'Needs reply' }));
    await waitFor(() => expect(api.getReviews).toHaveBeenLastCalledWith('s1', { rating: 3, needsReply: true, limit: 10 }));
    expect(await screen.findByText('You have replied to every review here.')).toBeInTheDocument();
  });

  it('posts and edits a reply inline, with a confirmation', async () => {
    api.getReviews.mockResolvedValue({ items: [review('r1')], total: 1 });
    const replied = review('r1', { reply: { text: 'Thank you, Priya!', createdAt: '2026-10-15T10:00:00Z', updatedAt: '2026-10-15T10:00:00Z' } });
    api.replyToReview.mockResolvedValueOnce(replied);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Reply to Priya S.' }));
    const box = screen.getByLabelText('Your public reply');
    fireEvent.click(screen.getByRole('button', { name: 'Post reply' }));
    expect(await screen.findByText('Write a reply first')).toBeInTheDocument();
    expect(api.replyToReview).not.toHaveBeenCalled();

    fireEvent.change(box, { target: { value: 'Thank you, Priya!' } });
    expect(screen.getByText('17/1000')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Post reply' }));
    expect(await screen.findByText('Reply posted. Customers will see it under the review.')).toBeInTheDocument();
    expect(api.replyToReview).toHaveBeenCalledWith('s1', 'r1', 'Thank you, Priya!');
    expect(screen.getByText('Thank you, Priya!')).toBeInTheDocument();

    api.replyToReview.mockResolvedValueOnce({ ...replied, reply: { ...replied.reply!, text: 'Thanks a lot!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Edit reply to Priya S.' }));
    expect(screen.getByLabelText('Your public reply')).toHaveValue('Thank you, Priya!');
    fireEvent.change(screen.getByLabelText('Your public reply'), { target: { value: 'Thanks a lot!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save reply' }));
    expect(await screen.findByText('Reply updated.')).toBeInTheDocument();
    expect(screen.getByText('Thanks a lot!')).toBeInTheDocument();
  });

  it('keeps the reply open with the reason when saving fails', async () => {
    api.getReviews.mockResolvedValue({ items: [review('r1')], total: 1 });
    api.replyToReview.mockRejectedValue({ response: { data: { detail: 'Not your shop' } } });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Reply to Priya S.' }));
    fireEvent.change(screen.getByLabelText('Your public reply'), { target: { value: 'Hi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Post reply' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Not your shop');
    expect(screen.getByLabelText('Your public reply')).toHaveValue('Hi');
  });

  it('explains an empty page to a new shop', async () => {
    api.getReviewSummary.mockResolvedValue({ ...summary, averageRating: 0, reviewCount: 0, distribution: summary.distribution.map((d) => ({ ...d, count: 0 })) });
    api.getReviews.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    expect(await screen.findByText('No reviews yet. Customers can review you after a completed booking.')).toBeInTheDocument();
    expect(screen.getAllByText('No reviews yet').length).toBeGreaterThan(0);
  });
});
