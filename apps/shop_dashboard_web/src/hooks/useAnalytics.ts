import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { getShopSummary } from '../services/bookingService';
import { apiErrorMessage } from '../services/format';
import type { Analytics } from '../types';

interface UseAnalyticsResult {
  analytics: Analytics | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Booking summary for the signed-in owner's shop (defaults to the last 30 days). */
export function useAnalytics(dateFrom?: string, dateTo?: string): UseAnalyticsResult {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    getShopSummary(shopId, dateFrom, dateTo)
      .then((data) => {
        if (!cancelled) setAnalytics(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(apiErrorMessage(err, 'Could not load analytics'));
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [shopId, dateFrom, dateTo, tick]);

  const refetch = () => setTick((t) => t + 1);

  return { analytics, isLoading, error, refetch };
}
