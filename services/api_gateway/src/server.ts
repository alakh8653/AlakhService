import { createClient } from 'redis';
import { createApp } from './app.js';
import { loadConfig } from './config.js';
import type { SendCommand } from './revocation.js';

const config = loadConfig();

function connectRedis(url: string): SendCommand {
  const client = createClient({
    url,
    // While Redis is down, commands fail at once (limits and revocations then let requests
    // through) instead of queueing and holding every request; the client keeps reconnecting.
    disableOfflineQueue: true,
    socket: { connectTimeout: 2_000, reconnectStrategy: (retries) => Math.min(retries * 200, 5_000) },
  });
  client.on('error', (err: Error) => console.error(JSON.stringify({ msg: 'redis_error', error: err.message })));
  client.connect().catch(() => undefined); // reported by the error handler; reconnects on its own
  return (args) => client.sendCommand(args);
}

const redis = config.redisUrl ? connectRedis(config.redisUrl) : undefined;
const server = createApp(config, { redis, processMetrics: true }).listen(config.port, () => {
  console.log(JSON.stringify({ msg: 'api_gateway listening', port: config.port, sharedLimits: Boolean(redis) }));
});

for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.on(signal, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 10_000).unref();
  });
}
