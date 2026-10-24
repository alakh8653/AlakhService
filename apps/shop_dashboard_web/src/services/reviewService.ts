import apiClient from './apiClient';

// ── Reviews (shop_service) ───────────────────────────────────────────────────

export interface RatingSummary {
  averageRating: number;
  reviewCount: number;
  /** Count per star level, 5 stars first. */
  distribution: { stars: number; count: number }[];
}

export interface OwnerReply {
  text: string;
  createdAt: string;
  updatedAt: string;
}

export interface Review {
  id: string;
  shopId: string;
  serviceId: string | null;
  rating: number;
  comment: string | null;
  /** First name and last initial, as customers see it. */
  reviewerName: string;
  createdAt: string;
  reply: OwnerReply | null;
}

export interface ReviewPage {
  items: Review[];
  total: number;
}

interface SummaryResponse {
  average_rating: number;
  review_count: number;
  distribution: { stars: number; count: number }[];
}

interface ReviewResponse {
  id: string;
  shop_id: string;
  service_id: string | null;
  rating: number;
  comment: string | null;
  reviewer_name: string;
  created_at: string;
  reply: { text: string; created_at: string; updated_at: string } | null;
}

export function toReview(data: ReviewResponse): Review {
  return {
    id: data.id,
    shopId: data.shop_id,
    serviceId: data.service_id,
    rating: data.rating,
    comment: data.comment,
    reviewerName: data.reviewer_name,
    createdAt: data.created_at,
    reply: data.reply ? { text: data.reply.text, createdAt: data.reply.created_at, updatedAt: data.reply.updated_at } : null,
  };
}

const reviewsPath = (shopId: string) => `/shops/${encodeURIComponent(shopId)}/reviews`;

export async function getReviewSummary(shopId: string): Promise<RatingSummary> {
  const { data } = await apiClient.get<SummaryResponse>(`${reviewsPath(shopId)}/summary`);
  return { averageRating: data.average_rating, reviewCount: data.review_count, distribution: data.distribution };
}

export interface ReviewFilters {
  rating?: number | null;
  needsReply?: boolean;
  skip?: number;
  limit?: number;
}

/** Newest first. */
export async function getReviews(shopId: string, filters: ReviewFilters = {}): Promise<ReviewPage> {
  const params: Record<string, unknown> = { skip: filters.skip ?? 0, limit: filters.limit ?? 10 };
  if (filters.rating) params.rating = filters.rating;
  if (filters.needsReply) params.needs_reply = true;
  const { data } = await apiClient.get<{ items: ReviewResponse[]; total: number }>(reviewsPath(shopId), { params });
  return { items: data.items.map(toReview), total: data.total };
}

/** Posts the shop's public reply, or edits it if there is one. */
export async function replyToReview(shopId: string, reviewId: string, text: string): Promise<Review> {
  const { data } = await apiClient.put<ReviewResponse>(`${reviewsPath(shopId)}/${encodeURIComponent(reviewId)}/reply`, {
    text: text.trim(),
  });
  return toReview(data);
}
