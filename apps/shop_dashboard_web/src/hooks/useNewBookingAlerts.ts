import { useEffect, useRef } from 'react';
import { useToast } from '../components/Toast';
import { getShopBookings } from '../services/bookingService';
import { installAudioUnlock, playChime } from '../services/alertSound';
import { formatWhen } from '../services/format';

export const POLL_MS = 30_000;

/**
 * Checks for new PENDING bookings every 30 seconds while the dashboard is open and announces each new
 * one with a toast and (unless muted, and once the browser allows sound) a chime. The bookings already
 * waiting when the dashboard opens are not announced.
 */
export function useNewBookingAlerts(shopId: string | undefined, onNew?: () => void): void {
  const notify = useToast();
  const seen = useRef<Set<string> | null>(null);
  const onNewRef = useRef(onNew);
  onNewRef.current = onNew;

  useEffect(() => {
    if (!shopId) return;
    installAudioUnlock();
    seen.current = null;
    let stopped = false;
    let running = false;

    const check = async () => {
      if (running) return;
      running = true;
      try {
        const page = await getShopBookings(shopId, { status: 'PENDING', perPage: 50 });
        if (stopped) return;
        const known = seen.current;
        const fresh = known ? page.data.filter((b) => !known.has(b.id)) : [];
        seen.current = new Set([...(known ?? []), ...page.data.map((b) => b.id)]);
        if (fresh.length > 0) {
          notify(
            fresh.length === 1
              ? `New booking from ${fresh[0].customerDisplayName || 'a customer'} for ${formatWhen(fresh[0].scheduledAt)}. Please confirm it.`
              : `${fresh.length} new bookings are waiting for you to confirm.`,
          );
          playChime();
          onNewRef.current?.();
        }
      } catch {
        // Offline or the booking service is down: try again on the next tick, quietly.
      } finally {
        running = false;
      }
    };

    void check();
    const timer = window.setInterval(() => void check(), POLL_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [shopId, notify]);
}
