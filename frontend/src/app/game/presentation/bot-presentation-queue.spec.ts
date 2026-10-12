import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BotPresentationEvent } from '../../core/api/game-api.models';
import { BotPresentationQueue } from './bot-presentation-queue';

const event = (type: BotPresentationEvent['type']): BotPresentationEvent => ({
  type,
  actor: 'BOT',
  actor_seat: 'two',
  card_count: 1,
  value: 6,
  target: null,
  cards: [],
});

describe('BotPresentationQueue', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('presents every public action in order and unlocks only after the final event', () => {
    const queue = new BotPresentationQueue();
    const complete = vi.fn();

    queue.play([event('BOT_INITIAL_ATTACK'), event('BOT_TRANSFER'), event('BOT_BITO')], complete);

    expect(queue.locked()).toBe(true);
    expect(queue.current()?.type).toBe('BOT_INITIAL_ATTACK');
    vi.advanceTimersByTime(1_500);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    vi.advanceTimersByTime(1_800);
    expect(queue.current()?.type).toBe('BOT_BITO');
    vi.advanceTimersByTime(600);
    expect(queue.current()).toBeNull();
    expect(queue.locked()).toBe(false);
    expect(complete).toHaveBeenCalledOnce();
  });

  it('keeps reduced-motion actions sequential while shortening their presentation', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    const queue = new BotPresentationQueue();
    queue.play([event('BOT_TAKE'), event('BOT_DEFEND')]);

    expect(queue.current()?.type).toBe('BOT_TAKE');
    vi.advanceTimersByTime(1_440);
    expect(queue.current()?.type).toBe('BOT_DEFEND');
    vi.advanceTimersByTime(1_280);
    expect(queue.locked()).toBe(false);
    vi.unstubAllGlobals();
  });

  it('accelerates long backlogs without dropping significant events', () => {
    const queue = new BotPresentationQueue();
    const events = Array.from({ length: 20 }, () => event('BOT_TRANSFER'));
    queue.play(events);

    vi.advanceTimersByTime(19_999);
    expect(queue.locked()).toBe(true);
    vi.advanceTimersByTime(1);
    expect(queue.locked()).toBe(false);
  });

  it.each([
    ['relaxed', 2_000],
    ['normal', 1_500],
    ['fast', 500],
  ] as const)('uses the stored %s presentation dwell', (speed, duration) => {
    const queue = new BotPresentationQueue();
    queue.setSpeed(speed);
    queue.play([event('BOT_INITIAL_ATTACK')]);

    vi.advanceTimersByTime(duration - 1);
    expect(queue.locked()).toBe(true);
    vi.advanceTimersByTime(1);
    expect(queue.locked()).toBe(false);
    expect(localStorage.getItem('kiba.botPresentationSpeed')).toBe(speed);
  });

  it('applies a speed change only to future steps without replaying or reordering', () => {
    const queue = new BotPresentationQueue();
    const seen: BotPresentationEvent['type'][] = [];
    queue.play(
      [event('BOT_INITIAL_ATTACK'), event('BOT_TRANSFER'), event('BOT_DEFEND')],
      undefined,
      (step) => seen.push(step.type),
    );

    vi.advanceTimersByTime(1_500);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    queue.setSpeed('fast');
    vi.advanceTimersByTime(1_799);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    vi.advanceTimersByTime(1);
    expect(queue.current()?.type).toBe('BOT_DEFEND');
    vi.advanceTimersByTime(550);
    expect(queue.locked()).toBe(false);
    expect(seen).toEqual(['BOT_INITIAL_ATTACK', 'BOT_TRANSFER', 'BOT_DEFEND']);
  });
});
