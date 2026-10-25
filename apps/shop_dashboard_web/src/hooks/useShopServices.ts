import { useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { getServices } from '../services/shopService';
import { apiErrorMessage } from '../services/format';
import type { Service } from '../types';

/** The shop's catalogue (active and inactive), plus an id → name lookup. */
export function useShopServices() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [services, setServices] = useState<Service[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    getServices(shopId)
      .then((data) => {
        if (!cancelled) setServices(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setServices([]);
          setError(apiErrorMessage(err, 'Could not load your services'));
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  const serviceNames = useMemo(
    () => Object.fromEntries(services.map((s) => [s.id, s.name])) as Record<string, string>,
    [services],
  );

  return { services, setServices, serviceNames, isLoading, error };
}
