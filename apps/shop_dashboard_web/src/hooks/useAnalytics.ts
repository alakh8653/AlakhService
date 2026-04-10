import { useEffect, useState } from 'react';
import apiClient from '../services/apiClient';
import type { Analytics } from '../types';

interface UseAnalyticsResult {
  analytics: Analytics | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useAnalytics(
  dateFrom?: string,
  dateTo?: string,
): UseAnalyticsResult {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    apiClient
      .get<Analytics>('/analytics/summary', {
        params: { dateFrom, dateTo },
      })
      .then(({ data }) => {
        if (!cancelled) setAnalytics(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo, tick]);

  const refetch = () => setTick((t) => t + 1);

  return { analytics, isLoading, error, refetch };
}
