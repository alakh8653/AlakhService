import { useEffect, useState } from 'react';
import { getShopQueue, type QueueEntry } from '../services/bookingService';

const REFRESH_MS = 60_000;

/** Today's live queue at the shop by booking id, refreshed every minute (and when [refreshKey] changes). */
export function useShopQueue(shopId: string | undefined, refreshKey: unknown = 0): Record<string, QueueEntry> {
  const [queue, setQueue] = useState<Record<string, QueueEntry>>({});
  useEffect(() => {
    if (!shopId) return;
    let live = true;
    const load = () =>
      getShopQueue(shopId)
        .then((entries) => live && setQueue(Object.fromEntries(entries.map((e) => [e.bookingId, e]))))
        .catch(() => undefined); // the cards show their booked times as before
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [shopId, refreshKey]);
  return queue;
}
