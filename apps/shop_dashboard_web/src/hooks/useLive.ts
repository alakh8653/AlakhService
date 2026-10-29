import { useCallback, useEffect, useRef, useState } from 'react';

const POLL_MS = 30_000;
const MAX_BACKOFF_MS = 30_000;

/**
 * Data kept live from a WebSocket that sends whole snapshots ([parse] turns a frame into one, or null to
 * ignore it), with [load] for the first look, after every action and while the socket is down. The
 * socket reconnects with backoff (1 s, 2 s, 4 s... up to 30 s); until it is back, [load] runs every 30 s.
 */
export function useLive<T>(url: string | null, parse: (frame: unknown) => T | null, load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [connected, setConnected] = useState(false);
  const parseRef = useRef(parse);
  const loadRef = useRef(load);
  parseRef.current = parse;
  loadRef.current = load;

  const refresh = useCallback(async () => {
    try {
      setData(await loadRef.current());
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, url]);

  useEffect(() => {
    if (!url || typeof WebSocket === 'undefined') return;
    let socket: WebSocket | null = null;
    let stopped = false;
    let attempt = 0;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const open = () => {
      socket = new WebSocket(url);
      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
      };
      socket.onmessage = (event) => {
        try {
          const next = parseRef.current(JSON.parse(String(event.data)));
          if (next !== null) setData(next);
        } catch {
          // a frame we do not understand: keep what we have
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        retry = setTimeout(open, Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt++));
      };
    };
    open();
    return () => {
      stopped = true;
      clearTimeout(retry);
      socket?.close();
    };
  }, [url]);

  useEffect(() => {
    if (connected) return;
    const timer = setInterval(() => !document.hidden && void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [connected, refresh]);

  return { data, error, connected, refresh };
}
