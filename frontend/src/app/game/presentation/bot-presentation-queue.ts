import { Injectable, signal } from '@angular/core';
import { BotPresentationEvent } from '../../core/api/game-api.models';

export type BotPresentationSpeed = 'relaxed' | 'normal' | 'fast';

const SPEED_STORAGE_KEY = 'kiba.botPresentationSpeed';
const TIMING_MS: Readonly<
  Record<BotPresentationSpeed, { readonly anticipation: number; readonly dwell: number }>
> = {
  fast: { anticipation: 150, dwell: 800 },
  normal: { anticipation: 300, dwell: 2_000 },
  relaxed: { anticipation: 450, dwell: 3_200 },
};

/** Presents already-confirmed public bot actions in server order without delaying the engine. */
@Injectable()
export class BotPresentationQueue {
  /** Current announced actor/action. Set before any card or table reveal. */
  readonly current = signal<BotPresentationEvent | null>(null);
  /** Last revealed authoritative presentation frame. */
  readonly revealed = signal<BotPresentationEvent | null>(null);
  readonly phase = signal<'idle' | 'anticipating' | 'dwelling'>('idle');
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
    this.revealed.set(null);
    this.phase.set('idle');
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
    this.phase.set('anticipating');
    const speed = this.speed();
    const timing = TIMING_MS[speed];
    this.timer = setTimeout(() => {
      this.revealed.set(event);
      this.phase.set('dwelling');
      this.onStep?.(event, eventIndex);
      this.timer = setTimeout(() => {
        this.timer = null;
        this.showNext();
      }, timing.dwell);
    }, timing.anticipation);
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
