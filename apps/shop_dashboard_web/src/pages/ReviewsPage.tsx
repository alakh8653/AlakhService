import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { format } from 'date-fns';
import { MessageSquareReply, Pencil, Star } from 'lucide-react';
import type { RootState } from '../state/store';
import { getReviewSummary, getReviews, replyToReview, type RatingSummary, type Review } from '../services/reviewService';
import { apiErrorMessage } from '../services/format';
import { useShopServices } from '../hooks/useShopServices';
import { useToast } from '../components/Toast';

const PAGE_SIZE = 10;
const MAX_REPLY = 1000;

/** "12 Oct 2026": day first, the way dates are written in India. */
export const reviewDate = (iso: string) => format(new Date(iso), 'd MMM yyyy');

export function Stars({ rating, size = 16 }: { rating: number; size?: number }) {
  return (
    <span role="img" aria-label={`${rating} out of 5 stars`} className="inline-flex">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          size={size}
          aria-hidden
          className={n <= Math.round(rating) ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}
        />
      ))}
    </span>
  );
}

export function RatingSummaryCard({ summary }: { summary: RatingSummary }) {
  const most = Math.max(1, ...summary.distribution.map((d) => d.count));
  return (
    <section aria-labelledby="summary-heading" className="bg-white rounded-2xl shadow p-4 md:p-5 flex flex-col sm:flex-row gap-4 sm:gap-8">
      <h2 id="summary-heading" className="sr-only">
        Rating summary
      </h2>
      <div className="text-center sm:text-left">
        <p className="text-4xl font-bold text-gray-900">{summary.reviewCount ? summary.averageRating.toFixed(1) : '–'}</p>
        <Stars rating={summary.averageRating} size={18} />
        <p className="text-sm text-gray-500 mt-1">
          {summary.reviewCount === 0
            ? 'No reviews yet'
            : `${summary.reviewCount} review${summary.reviewCount === 1 ? '' : 's'}`}
        </p>
      </div>
      <ul className="flex-1 space-y-1.5" aria-label="Reviews by star rating">
        {summary.distribution.map((d) => (
          <li key={d.stars} className="flex items-center gap-2 text-sm">
            <span className="w-8 text-gray-600 tabular-nums" aria-hidden>
              {d.stars}★
            </span>
            <span className="sr-only">
              {d.stars} star{d.stars === 1 ? '' : 's'}: {d.count}
            </span>
            <span className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden" aria-hidden>
              <span className="block h-full bg-yellow-400 rounded-full" style={{ width: `${(d.count / most) * 100}%` }} />
            </span>
            <span className="w-8 text-right text-gray-500 tabular-nums" aria-hidden>
              {d.count}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReplyEditor({ review, onSave, onCancel }: { review: Review; onSave: (text: string) => Promise<void>; onCancel: () => void }) {
  const [text, setText] = useState(review.reply?.text ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = `reply-${review.id}`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) {
      setError('Write a reply first');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(text);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save your reply'));
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-3 space-y-2" noValidate>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        Your public reply
      </label>
      <textarea
        id={id}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setError(null);
        }}
        maxLength={MAX_REPLY}
        rows={3}
        autoFocus
        aria-invalid={!!error}
        aria-describedby={`${id}-help`}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400"
        placeholder="Thank them, or say what you'll do about it. Everyone can read this."
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span id={`${id}-help`} className={`text-xs ${error ? 'text-red-600' : 'text-gray-500'}`} role={error ? 'alert' : undefined}>
          {error ?? `${text.length}/${MAX_REPLY}`}
        </span>
        <div className="flex gap-2 ml-auto">
          <button type="button" onClick={onCancel} className="px-3 py-2 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving…' : review.reply ? 'Save reply' : 'Post reply'}
          </button>
        </div>
      </div>
    </form>
  );
}

function ReviewItem({
  review,
  serviceName,
  onReplied,
}: {
  review: Review;
  serviceName?: string;
  onReplied: (r: Review) => void;
}) {
  const [editing, setEditing] = useState(false);
  const toast = useToast();

  const save = async (text: string) => {
    const updated = await replyToReview(review.shopId, review.id, text);
    onReplied(updated);
    setEditing(false);
    toast(review.reply ? 'Reply updated.' : 'Reply posted. Customers will see it under the review.');
  };

  return (
    <li>
      <article aria-label={`Review by ${review.reviewerName}`} className="bg-white rounded-2xl shadow p-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-medium text-gray-900">{review.reviewerName}</span>
          <Stars rating={review.rating} />
          <span className="text-xs text-gray-500">{reviewDate(review.createdAt)}</span>
        </div>
        {serviceName && <p className="text-xs text-gray-500 mt-0.5">{serviceName}</p>}
        {review.comment ? (
          <p className="mt-2 text-sm text-gray-800 whitespace-pre-line break-words">{review.comment}</p>
        ) : (
          <p className="mt-2 text-sm text-gray-500 italic">Rated without a written review.</p>
        )}
        {review.reply && !editing && (
          <div className="mt-3 border-l-4 border-indigo-200 bg-indigo-50/60 rounded-r-lg px-3 py-2">
            <p className="text-xs font-medium text-indigo-800">
              Your reply · {reviewDate(review.reply.updatedAt)}
            </p>
            <p className="text-sm text-gray-800 whitespace-pre-line break-words">{review.reply.text}</p>
          </div>
        )}
        {editing ? (
          <ReplyEditor review={review} onSave={save} onCancel={() => setEditing(false)} />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:underline"
            aria-label={review.reply ? `Edit reply to ${review.reviewerName}` : `Reply to ${review.reviewerName}`}
          >
            {review.reply ? <Pencil size={14} aria-hidden /> : <MessageSquareReply size={14} aria-hidden />}
            {review.reply ? 'Edit reply' : 'Reply'}
          </button>
        )}
      </article>
    </li>
  );
}

const chip = (active: boolean) =>
  `px-3 py-1.5 rounded-full text-sm font-medium border whitespace-nowrap ${
    active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
  }`;

export default function ReviewsPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { serviceNames } = useShopServices();
  const [summary, setSummary] = useState<RatingSummary | null>(null);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [total, setTotal] = useState(0);
  const [rating, setRating] = useState<number | null>(null);
  const [needsReply, setNeedsReply] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    getReviewSummary(shopId)
      .then((s) => !cancelled && setSummary(s))
      .catch((err: unknown) => !cancelled && setError(apiErrorMessage(err, 'Could not load your reviews')));
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    setReviews(null);
    getReviews(shopId, { rating, needsReply, limit: PAGE_SIZE })
      .then((page) => {
        if (cancelled) return;
        setReviews(page.items);
        setTotal(page.total);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReviews([]);
          setError(apiErrorMessage(err, 'Could not load your reviews'));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [shopId, rating, needsReply]);

  const loadMore = async () => {
    if (!shopId || !reviews) return;
    setLoadingMore(true);
    try {
      const page = await getReviews(shopId, { rating, needsReply, skip: reviews.length, limit: PAGE_SIZE });
      setReviews((list) => [...(list ?? []), ...page.items.filter((r) => !list?.some((x) => x.id === r.id))]);
      setTotal(page.total);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not load more reviews'));
    } finally {
      setLoadingMore(false);
    }
  };

  const replace = useCallback((r: Review) => setReviews((list) => list?.map((x) => (x.id === r.id ? r : x)) ?? null), []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reviews</h1>
        <p className="text-sm text-gray-500">What customers say after a completed booking. Replies are public.</p>
      </div>

      {summary ? (
        <RatingSummaryCard summary={summary} />
      ) : (
        !error && <div className="bg-white rounded-2xl shadow h-32 animate-pulse" aria-label="Loading rating summary" />
      )}

      <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1" role="group" aria-label="Filter reviews">
        <button type="button" className={chip(rating === null)} aria-pressed={rating === null} onClick={() => setRating(null)}>
          All
        </button>
        {[5, 4, 3, 2, 1].map((n) => (
          <button
            key={n}
            type="button"
            className={chip(rating === n)}
            aria-pressed={rating === n}
            aria-label={`${n} star${n === 1 ? '' : 's'}`}
            onClick={() => setRating(rating === n ? null : n)}
          >
            {n}★
          </button>
        ))}
        <button type="button" className={chip(needsReply)} aria-pressed={needsReply} onClick={() => setNeedsReply((v) => !v)}>
          Needs reply
        </button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {reviews === null ? (
        <div className="bg-white rounded-2xl shadow h-24 animate-pulse" aria-label="Loading reviews" />
      ) : reviews.length === 0 ? (
        !error && (
          <p className="bg-white rounded-2xl shadow p-6 text-center text-gray-500">
            {needsReply
              ? 'You have replied to every review here.'
              : rating || summary?.reviewCount
                ? 'No reviews match these filters.'
                : 'No reviews yet. Customers can review you after a completed booking.'}
          </p>
        )
      ) : (
        <>
          <p className="text-sm text-gray-500" aria-live="polite">
            Showing {reviews.length} of {total}
          </p>
          <ul className="space-y-3">
            {reviews.map((r) => (
              <ReviewItem key={r.id} review={r} serviceName={r.serviceId ? serviceNames[r.serviceId] : undefined} onReplied={replace} />
            ))}
          </ul>
          {reviews.length < total && (
            <div className="text-center">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                {loadingMore ? 'Loading…' : 'Show more reviews'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
