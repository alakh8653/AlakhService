/**
 * Per-upstream circuit breaker.
 *
 * closed    – requests flow; consecutive failures are counted.
 * open      – after `failureThreshold` consecutive failures requests are rejected
 *             immediately for `resetTimeoutMs`.
 * half-open – after the timeout one trial request is let through; success closes the
 *             circuit, failure opens it again.
 */
export type BreakerState = 'closed' | 'open' | 'half-open';

export class CircuitBreaker {
  private state: BreakerState = 'closed';
  private failures = 0;
  private openedAt = 0;
  private trialInFlight = false;

  constructor(
    private readonly failureThreshold: number,
    private readonly resetTimeoutMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  get currentState(): BreakerState {
    if (this.state === 'open' && this.now() - this.openedAt >= this.resetTimeoutMs) {
      return 'half-open';
    }
    return this.state;
  }

  /** Milliseconds until an open circuit lets a trial request through. */
  retryAfterMs(): number {
    return Math.max(0, this.openedAt + this.resetTimeoutMs - this.now());
  }

  /** Returns true if a request may be sent now (and reserves the half-open trial). */
  tryAcquire(): boolean {
    const state = this.currentState;
    if (state === 'closed') return true;
    if (state === 'half-open' && !this.trialInFlight) {
      this.state = 'half-open';
      this.trialInFlight = true;
      return true;
    }
    return false;
  }

  onSuccess(): void {
    this.state = 'closed';
    this.failures = 0;
    this.trialInFlight = false;
  }

  onFailure(): void {
    this.trialInFlight = false;
    this.failures += 1;
    if (this.state === 'half-open' || this.failures >= this.failureThreshold) {
      this.state = 'open';
      this.openedAt = this.now();
    }
  }
}
