import { Injectable, signal } from '@angular/core';
import { BotPresentationEvent } from '../../core/api/game-api.models';

export type BotPresentationSpeed = 'relaxed' | 'normal' | 'fast';

const SPEED_STORAGE_KEY = 'kiba.botPresentationSpeed';
const EVENT_MS: Readonly<
  Record<BotPresentationSpeed, Readonly<Record<BotPresentationEvent['type'], number>>>
> = {
  relaxed: {
    BOT_INITIAL_ATTACK: 2_000,
    BOT_DEFEND: 2_100,
    BOT_TRANSFER: 2_300,
    BOT_THROW_IN: 2_100,
    BOT_TAKE: 2_300,
    BOT_BITO: 800,
  },
  normal: {
    BOT_INITIAL_ATTACK: 1_500,
    BOT_DEFEND: 1_600,
    BOT_TRANSFER: 1_800,
    BOT_THROW_IN: 1_650,
    BOT_TAKE: 1_800,
    BOT_BITO: 600,
  },
  fast: {
    BOT_INITIAL_ATTACK: 500,
    BOT_DEFEND: 550,
    BOT_TRANSFER: 650,
    BOT_THROW_IN: 550,
    BOT_TAKE: 700,
    BOT_BITO: 350,
  },
};
const MAX_SEQUENCE_MS: Readonly<Record<BotPresentationSpeed, number>> = {
  relaxed: 30_000,
  normal: 20_000,
  fast: 9_000,
};
const REDUCED_MOTION_SCALE = 0.8;
const MIN_REDUCED_MOTION_DWELL_MS = 600;

/** Presents already-confirmed public bot actions in server order without delaying the engine. */
@Injectable()
export class BotPresentationQueue {
  readonly current = signal<BotPresentationEvent | null>(null);
  readonly locked = signal(false);
  readonly speed = signal<BotPresentationSpeed>(this.readSpeed());
  private timer: ReturnType<typeof setTimeout> | null = null;
  private events: readonly BotPresentationEvent[] = [];
  private index = 0;
  private onComplete: (() => void) | null = null;
  private onStep: ((event: BotPresentationEvent, index: number) => void) | null = null;

  play(
    events: readonly BotPresentationEvent[],
    onComplete?: () => void,
    onStep?: (event: BotPresentationEvent, index: number) => void,
  ): void {
    this.clear();
    if (events.length === 0) {
      onComplete?.();
      return;
    }
    this.events = [...events];
    this.onComplete = onComplete ?? null;
    this.onStep = onStep ?? null;
    this.locked.set(true);
    this.showNext();
  }

  setSpeed(speed: BotPresentationSpeed): void {
    this.speed.set(speed);
    try {
      localStorage.setItem(SPEED_STORAGE_KEY, speed);
    } catch {
      // Presentation remains usable when browser storage is unavailable.
    }
  }

  clear(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.events = [];
    this.index = 0;
    this.current.set(null);
    this.locked.set(false);
    this.onComplete = null;
    this.onStep = null;
  }

  private showNext(): void {
    const eventIndex = this.index;
    const event = this.events[this.index++] ?? null;
    if (event === null) {
      const complete = this.onComplete;
      this.clear();
      complete?.();
      return;
    }
    this.current.set(event);
    this.onStep?.(event, eventIndex);
    const speed = this.speed();
    const preferredTotal = this.events.reduce(
      (total, queuedEvent) => total + EVENT_MS[speed][queuedEvent.type],
      0,
    );
    const scale = Math.min(1, MAX_SEQUENCE_MS[speed] / preferredTotal);
    const reducedMotion =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const duration = reducedMotion
      ? Math.max(
          MIN_REDUCED_MOTION_DWELL_MS,
          Math.round(EVENT_MS[speed][event.type] * REDUCED_MOTION_SCALE * scale),
        )
      : Math.round(EVENT_MS[speed][event.type] * scale);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.showNext();
    }, duration);
  }

  private readSpeed(): BotPresentationSpeed {
    try {
      const stored = localStorage.getItem(SPEED_STORAGE_KEY);
      if (stored === 'relaxed' || stored === 'normal' || stored === 'fast') return stored;
    } catch {
      // Use the stable default when browser storage is unavailable.
    }
    return 'normal';
  }
}
