import { useSyncExternalStore } from 'react';

// The chime for a new booking. Browsers only let a page make sound after the person has interacted
// with it, so the audio context is created on the first click or key press, never before; until then
// (and when muted) new bookings show only a toast.

const MUTE_KEY = 'shop_alerts_muted';
const listeners = new Set<() => void>();

function readMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === '1';
  } catch {
    return false;
  }
}

let muted = readMuted();

export function isMuted(): boolean {
  return muted;
}

export function setMuted(value: boolean): void {
  muted = value;
  try {
    if (value) localStorage.setItem(MUTE_KEY, '1');
    else localStorage.removeItem(MUTE_KEY);
  } catch {
    // private mode: the choice lasts for this visit only
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** [muted, setMuted], shared by every component (the header toggle and the booking poller). */
export function useMuted(): [boolean, (value: boolean) => void] {
  return [useSyncExternalStore(subscribe, isMuted, isMuted), setMuted];
}

type AudioContextCtor = typeof AudioContext;
let context: AudioContext | null = null;
let unlockInstalled = false;

function audioCtor(): AudioContextCtor | undefined {
  if (typeof window === 'undefined') return undefined;
  return window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
}

/** Waits for the first user gesture and only then creates (or resumes) the audio context. */
export function installAudioUnlock(): void {
  if (unlockInstalled || typeof document === 'undefined') return;
  unlockInstalled = true;
  const unlock = () => {
    const Ctor = audioCtor();
    if (!Ctor) return;
    try {
      context ??= new Ctor();
      void context.resume?.();
    } catch {
      context = null;
    }
    document.removeEventListener('pointerdown', unlock);
    document.removeEventListener('keydown', unlock);
  };
  document.addEventListener('pointerdown', unlock);
  document.addEventListener('keydown', unlock);
}

/** Two short tones; returns whether a sound was played. */
export function playChime(): boolean {
  if (muted || !context || context.state !== 'running') return false;
  try {
    const now = context.currentTime;
    [880, 1320].forEach((freq, i) => {
      const osc = context!.createOscillator();
      const gain = context!.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + i * 0.18);
      gain.gain.exponentialRampToValueAtTime(0.25, now + i * 0.18 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.18 + 0.16);
      osc.connect(gain).connect(context!.destination);
      osc.start(now + i * 0.18);
      osc.stop(now + i * 0.18 + 0.17);
    });
    return true;
  } catch {
    return false;
  }
}

/** For tests. */
export function resetAudioForTests(ctx: AudioContext | null = null): void {
  context = ctx;
  unlockInstalled = false;
  muted = readMuted();
}
