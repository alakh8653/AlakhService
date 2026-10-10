import { useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { getServices } from '../services/shopService';
import type { Service } from '../types';

/** The shop's catalogue (active and inactive), plus an id → name lookup. */
export function useShopServices() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [services, setServices] = useState<Service[]>([]);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    getServices(shopId)
      .then((data) => {
        if (!cancelled) setServices(data);
      })
      .catch(() => {
        if (!cancelled) setServices([]);
      });
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  const serviceNames = useMemo(
    () => Object.fromEntries(services.map((s) => [s.id, s.name])) as Record<string, string>,
    [services],
  );

  return { services, setServices, serviceNames };
}
