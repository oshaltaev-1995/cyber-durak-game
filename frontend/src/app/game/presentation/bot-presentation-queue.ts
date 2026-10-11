import { Injectable, signal } from '@angular/core';
import { BotPresentationEvent } from '../../core/api/game-api.models';

const BASE_EVENT_MS: Readonly<Record<BotPresentationEvent['type'], number>> = {
  BOT_INITIAL_ATTACK: 500,
  BOT_DEFEND: 600,
  BOT_TRANSFER: 800,
  BOT_THROW_IN: 650,
  BOT_TAKE: 850,
  BOT_BITO: 600,
};
const MAX_SEQUENCE_MS = 6500;
const MIN_EVENT_MS = 300;

/** Presents already-confirmed public bot actions in server order without delaying the engine. */
@Injectable()
export class BotPresentationQueue {
  readonly current = signal<BotPresentationEvent | null>(null);
  readonly locked = signal(false);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private events: readonly BotPresentationEvent[] = [];
  private index = 0;
  private scale = 1;
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
    const preferredTotal = events.reduce((total, event) => total + BASE_EVENT_MS[event.type], 0);
    this.scale = Math.min(1, MAX_SEQUENCE_MS / preferredTotal);
    this.onComplete = onComplete ?? null;
    this.onStep = onStep ?? null;
    this.locked.set(true);
    this.showNext();
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
    const reducedMotion =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const duration = reducedMotion
      ? MIN_EVENT_MS
      : Math.max(MIN_EVENT_MS, Math.round(BASE_EVENT_MS[event.type] * this.scale));
    this.timer = setTimeout(() => {
      this.timer = null;
      this.showNext();
    }, duration);
  }
}
