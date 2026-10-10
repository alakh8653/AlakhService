import { describe, expect, it } from 'vitest';
import { CircuitBreaker } from '../src/circuitBreaker.js';

function breakerWithClock(threshold = 2, resetMs = 1_000) {
  const clock = { now: 0 };
  return { clock, breaker: new CircuitBreaker(threshold, resetMs, () => clock.now) };
}

describe('CircuitBreaker', () => {
  it('opens after consecutive failures and rejects requests', () => {
    const { breaker } = breakerWithClock();
    breaker.onFailure();
    expect(breaker.tryAcquire()).toBe(true);
    breaker.onFailure();
    expect(breaker.currentState).toBe('open');
    expect(breaker.tryAcquire()).toBe(false);
  });

  it('a success resets the failure count', () => {
    const { breaker } = breakerWithClock();
    breaker.onFailure();
    breaker.onSuccess();
    breaker.onFailure();
    expect(breaker.currentState).toBe('closed');
  });

  it('lets exactly one trial through after the reset timeout', () => {
    const { breaker, clock } = breakerWithClock();
    breaker.onFailure();
    breaker.onFailure();
    clock.now = 1_000;
    expect(breaker.currentState).toBe('half-open');
    expect(breaker.tryAcquire()).toBe(true);
    expect(breaker.tryAcquire()).toBe(false);
    breaker.onSuccess();
    expect(breaker.currentState).toBe('closed');
  });

  it('re-opens when the trial fails', () => {
    const { breaker, clock } = breakerWithClock();
    breaker.onFailure();
    breaker.onFailure();
    clock.now = 1_000;
    breaker.tryAcquire();
    breaker.onFailure();
    expect(breaker.currentState).toBe('open');
    expect(breaker.retryAfterMs()).toBe(1_000);
  });
});
