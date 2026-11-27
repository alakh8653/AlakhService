import { createClient } from 'redis';
import { createApp } from './app.js';
import { loadConfig } from './config.js';
import type { SendCommand } from './revocation.js';
import { attachWebSockets } from './websocket.js';

const config = loadConfig();

/** How long start-up waits for Redis before serving without it (it keeps reconnecting). */
const REDIS_START_WAIT_MS = 3_000;

async function connectRedis(url: string): Promise<SendCommand> {
  const client = createClient({
    url,
    // While Redis is down, commands fail at once (limits and revocations then let requests
    // through) instead of queueing and holding every request; the client keeps reconnecting.
    disableOfflineQueue: true,
    socket: { connectTimeout: 2_000, reconnectStrategy: (retries) => Math.min(retries * 200, 5_000) },
  });
  client.on('error', (err: Error) => console.error(JSON.stringify({ msg: 'redis_error', error: err.message })));
  // Failures are reported by the error handler and the client reconnects on its own. Waiting briefly
  // for the first connection lets the rate-limit stores load their script at start-up instead of
  // logging a failure and loading it on the first request.
  const connected = client.connect().catch(() => undefined);
  let timer: NodeJS.Timeout | undefined;
  await Promise.race([connected, new Promise((resolve) => (timer = setTimeout(resolve, REDIS_START_WAIT_MS)))]);
  clearTimeout(timer);
  return (args) => client.sendCommand(args);
}

const redis = config.redisUrl ? await connectRedis(config.redisUrl) : undefined;
const server = createApp(config, { redis, processMetrics: true }).listen(config.port, () => {
  console.log(JSON.stringify({ msg: 'api_gateway listening', port: config.port, sharedLimits: Boolean(redis) }));
});
// Live sockets (a booking's status, a shop's queue) go straight to booking_service.
attachWebSockets(server, config, { redis });

for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.on(signal, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 10_000).unref();
  });
}
