import { useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useLive } from '../hooks/useLive';
import { getBoard, liveUrl, toBoard, type Board } from '../services/liveQueueService';

/**
 * The screen in the shop (a TV or a spare tablet): who is being served and who is next, by ticket and a
 * masked name. Public, so the screen needs no account; it stays live on its own.
 */
export default function BoardPage() {
  const { shopId = '' } = useParams();
  const parse = useCallback((frame: unknown) => {
    const f = frame as { type?: string };
    return f.type === 'board' ? toBoard(f as Record<string, unknown>) : null;
  }, []);
  const load = useCallback(() => getBoard(shopId), [shopId]);
  const { data, error } = useLive<Board>(shopId ? liveUrl(shopId, 'board') : null, parse, load);

  return (
    <main className="min-h-dvh bg-gray-950 text-white p-6 md:p-12">
      {!data ? (
        <p role="status" className="text-2xl text-gray-400">
          {error ? 'This screen cannot reach the shop right now.' : 'Loading…'}
        </p>
      ) : (
        <div className="grid gap-10 lg:grid-cols-2">
          <section aria-label="Now serving">
            <h1 className="text-3xl md:text-5xl font-bold text-emerald-400 mb-6">Now serving</h1>
            {data.nowServing.length === 0 ? (
              <p className="text-2xl text-gray-400">Next customer, please.</p>
            ) : (
              <ul className="space-y-4">
                {data.nowServing.map((r) => (
                  <li key={r.ticket} className="flex items-baseline justify-between text-3xl md:text-5xl">
                    <span className="font-mono">{r.ticket}</span>
                    <span>{r.name}</span>
                    {r.staffName && <span className="text-xl md:text-3xl text-gray-300">{r.staffName}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Next">
            <h2 className="text-3xl md:text-5xl font-bold text-sky-400 mb-6">
              Next <span className="text-xl md:text-3xl text-gray-400 font-normal">({data.waiting} waiting)</span>
            </h2>
            {data.next.length === 0 ? (
              <p className="text-2xl text-gray-400">Nobody is waiting.</p>
            ) : (
              <ol className="space-y-3">
                {data.next.map((r) => (
                  <li key={r.ticket} className="flex items-baseline justify-between text-2xl md:text-4xl">
                    <span className="font-mono">{r.ticket}</span>
                    <span>{r.name}</span>
                    <span className="text-gray-300">{r.waitMinutes ? `~${r.waitMinutes} min` : 'now'}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
