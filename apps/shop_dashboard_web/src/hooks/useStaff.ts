import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { createStaffMember, getStaff } from '../services/shopService';
import type { StaffMember, User } from '../types';
import type { ProviderOption } from '../components/BookingCard';

/** One request per shop at a time, so two pages opening together add the owner only once. */
const addingOwner = new Map<string, Promise<StaffMember | null>>();

/**
 * The owner as the shop's own team member, as the app's setup does: home visits and pickups can only
 * be given to a team member with an account, so someone working alone needs this to take their own
 * jobs. Added only when the owner has no entry at all, so one they switched off stays off.
 */
export async function withOwnerOnTeam(shopId: string, owner: User, staff: StaffMember[]): Promise<StaffMember[]> {
  if (staff.some((m) => m.userId === owner.id)) return staff;
  let adding = addingOwner.get(shopId);
  if (!adding) {
    adding = createStaffMember(shopId, { name: owner.name || 'Owner', role: 'owner', userId: owner.id })
      .then((m) => m ?? null)
      .catch(() => null) // the shop still works; the owner can add themselves on the Staff page
      .finally(() => addingOwner.delete(shopId));
    addingOwner.set(shopId, adding);
  }
  const added = await adding;
  return added ? [...staff, added] : staff;
}

/**
 * The shop's staff, and those who can be given bookings (active, with a staff app account).
 * With ensureOwner, the owner is added to the team if they are not on it, so they can take jobs.
 */
export function useStaff({ ensureOwner = false }: { ensureOwner?: boolean } = {}) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const user = useSelector((state: RootState) => state.auth.user);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    getStaff(shopId)
      .then((list) => (ensureOwner && user ? withOwnerOnTeam(shopId, user, list) : list))
      .then((list) => {
        if (!cancelled) setStaff(list);
      })
      .catch(() => {
        if (!cancelled) setStaff([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [shopId, user, ensureOwner]);

  const providers = useMemo<ProviderOption[]>(
    () => staff.filter((m) => m.isActive && m.userId).map((m) => ({ userId: m.userId as string, name: m.name })),
    [staff],
  );

  const providerName = useCallback((userId: string) => staff.find((m) => m.userId === userId)?.name, [staff]);

  return { staff, setStaff, providers, providerName, isLoading };
}
