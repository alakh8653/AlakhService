import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { getReviews, getReviewSummary, replyToReview } from '../reviewService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const api = vi.mocked(apiClient);

const apiReview = {
  id: 'r1',
  shop_id: 's1',
  service_id: 'svc1',
  rating: 4,
  comment: 'Good',
  reviewer_name: 'Priya S.',
  created_at: '2026-10-12T09:30:00Z',
  reply: { text: 'Thanks!', created_at: '2026-10-13T09:30:00Z', updated_at: '2026-10-14T09:30:00Z' },
};

describe('reviewService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('reads the summary and a filtered page of reviews', async () => {
    api.get
      .mockResolvedValueOnce({ data: { average_rating: 4.6, review_count: 128, distribution: [{ stars: 5, count: 100 }] } })
      .mockResolvedValueOnce({ data: { items: [apiReview], total: 7 } })
      .mockResolvedValueOnce({ data: { items: [], total: 0 } });

    expect(await getReviewSummary('s1')).toEqual({ averageRating: 4.6, reviewCount: 128, distribution: [{ stars: 5, count: 100 }] });
    expect(api.get).toHaveBeenLastCalledWith('/shops/s1/reviews/summary');

    const page = await getReviews('s1', { rating: 4, needsReply: true, skip: 10 });
    expect(api.get).toHaveBeenLastCalledWith('/shops/s1/reviews', { params: { skip: 10, limit: 10, rating: 4, needs_reply: true } });
    expect(page.total).toBe(7);
    expect(page.items[0]).toEqual({
      id: 'r1', shopId: 's1', serviceId: 'svc1', rating: 4, comment: 'Good', reviewerName: 'Priya S.',
      createdAt: '2026-10-12T09:30:00Z',
      reply: { text: 'Thanks!', createdAt: '2026-10-13T09:30:00Z', updatedAt: '2026-10-14T09:30:00Z' },
    });

    // No filters: none are sent.
    await getReviews('s1');
    expect(api.get).toHaveBeenLastCalledWith('/shops/s1/reviews', { params: { skip: 0, limit: 10 } });
  });

  it('puts the reply trimmed, with ids kept to one path segment', async () => {
    api.put.mockResolvedValueOnce({ data: { ...apiReview, reply: null } });
    const review = await replyToReview('s/1', 'r1', '  Thank you!  ');
    expect(api.put).toHaveBeenCalledWith('/shops/s%2F1/reviews/r1/reply', { text: 'Thank you!' });
    expect(review.reply).toBeNull();
  });
});
