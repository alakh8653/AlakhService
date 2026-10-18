import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { getStaff } from '../services/shopService';
import type { StaffMember } from '../types';
import type { ProviderOption } from '../components/BookingCard';

/** The shop's staff, and those who can be given bookings (active, with a staff app account). */
export function useStaff() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [staff, setStaff] = useState<StaffMember[]>([]);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    getStaff(shopId)
      .then((list) => {
        if (!cancelled) setStaff(list);
      })
      .catch(() => {
        if (!cancelled) setStaff([]);
      });
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  const providers = useMemo<ProviderOption[]>(
    () => staff.filter((m) => m.isActive && m.userId).map((m) => ({ userId: m.userId as string, name: m.name })),
    [staff],
  );

  const providerName = useCallback((userId: string) => staff.find((m) => m.userId === userId)?.name, [staff]);

  return { staff, providers, providerName };
}
