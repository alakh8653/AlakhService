import { useCallback, useEffect, useState } from 'react';
import { useToast } from '../components/Toast';
import adminApiClient from '../apiClient';
import { apiErrorMessage } from '../shared/apiError';
import { formatDateTime } from '../shared/format';

// Reviews customers reported, which stay up until an admin hides them.

export interface ReportedReview {
  id: string;
  shop_id: string;
  rating: number;
  comment: string | null;
  reviewer_name: string;
  created_at: string;
  is_hidden: boolean;
  report_count: number;
  report_reasons: string[];
}

export async function getReportedReviews(hidden: boolean): Promise<ReportedReview[]> {
  const { data } = await adminApiClient.get<{ items: ReportedReview[] }>('/admin/reviews/reported', {
    params: { hidden, limit: 50 },
  });
  return data.items;
}

export async function setReviewHidden(id: string, hidden: boolean): Promise<void> {
  await adminApiClient.put(`/admin/reviews/${encodeURIComponent(id)}/visibility`, { hidden });
}

/** Keep a reported review, which clears its reports, or hide it, which also takes it out of the shop's average. */
export default function ReviewReportsPage() {
  const toast = useToast();
  const [hidden, setHidden] = useState(false);
  const [reviews, setReviews] = useState<ReportedReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReviews(await getReportedReviews(hidden));
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not load the reviews.'));
    } finally {
      setLoading(false);
    }
  }, [hidden]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (review: ReportedReview, hide: boolean) => {
    try {
      await setReviewHidden(review.id, hide);
      toast(hide ? 'Review hidden.' : 'Review kept, and its reports cleared.');
      await load();
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not save that.'), 'error');
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reported reviews</h1>
        <p className="text-sm text-gray-600">A reported review stays up until you hide it. Hiding also takes it out of the shop's rating.</p>
      </div>
      <div role="group" aria-label="Which reviews" className="flex gap-2">
        {[
          { value: false, label: 'Reported' },
          { value: true, label: 'Hidden' },
        ].map((tab) => (
          <button
            key={tab.label}
            type="button"
            aria-pressed={hidden === tab.value}
            onClick={() => setHidden(tab.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium ${hidden === tab.value ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {!loading && !error && reviews.length === 0 && <p className="text-sm text-gray-600">Nothing here.</p>}
      <ul className="space-y-3">
        {reviews.map((review) => (
          <li key={review.id} className="bg-white rounded-xl shadow p-4 space-y-2">
            <p className="text-sm font-semibold text-gray-900">
              {review.rating} of 5 from {review.reviewer_name}
            </p>
            {review.comment && <p className="text-sm text-gray-800">{review.comment}</p>}
            <p className="text-xs text-gray-500">{formatDateTime(review.created_at)}</p>
            {review.report_count > 0 && (
              <div className="text-sm text-amber-900 bg-amber-50 rounded-lg px-2 py-1">
                <p className="font-semibold">
                  Reported by {review.report_count} {review.report_count === 1 ? 'person' : 'people'}
                </p>
                <ul className="list-disc ml-4">
                  {review.report_reasons.map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex gap-2">
              <button type="button" onClick={() => void decide(review, false)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium">
                {review.is_hidden ? 'Show again' : 'Keep'}
              </button>
              {!review.is_hidden && (
                <button type="button" onClick={() => void decide(review, true)} className="rounded-lg bg-red-600 text-white px-3 py-1.5 text-sm font-medium">
                  Hide
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
