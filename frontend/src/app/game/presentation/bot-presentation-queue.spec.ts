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
    expect(queue.revealed()).toBeNull();
    expect(queue.phase()).toBe('anticipating');
    vi.advanceTimersByTime(299);
    expect(queue.revealed()).toBeNull();
    vi.advanceTimersByTime(1);
    expect(queue.revealed()?.type).toBe('BOT_INITIAL_ATTACK');
    expect(queue.phase()).toBe('dwelling');
    vi.advanceTimersByTime(2_000);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    expect(queue.revealed()?.type).toBe('BOT_INITIAL_ATTACK');
    vi.advanceTimersByTime(2_300);
    expect(queue.current()?.type).toBe('BOT_BITO');
    vi.advanceTimersByTime(2_300);
    expect(queue.current()).toBeNull();
    expect(queue.revealed()).toBeNull();
    expect(queue.locked()).toBe(false);
    expect(complete).toHaveBeenCalledOnce();
  });

  it('keeps reduced-motion actions sequential without removing readable dwell', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    const queue = new BotPresentationQueue();
    queue.play([event('BOT_TAKE'), event('BOT_DEFEND')]);

    expect(queue.current()?.type).toBe('BOT_TAKE');
    vi.advanceTimersByTime(2_300);
    expect(queue.current()?.type).toBe('BOT_DEFEND');
    vi.advanceTimersByTime(2_300);
    expect(queue.locked()).toBe(false);
    vi.unstubAllGlobals();
  });

  it('does not compress long backlogs below the selected stable dwell', () => {
    const queue = new BotPresentationQueue();
    const events = Array.from({ length: 20 }, () => event('BOT_TRANSFER'));
    queue.play(events);

    vi.advanceTimersByTime(45_999);
    expect(queue.locked()).toBe(true);
    vi.advanceTimersByTime(1);
    expect(queue.locked()).toBe(false);
  });

  it.each([
    ['relaxed', 3_650],
    ['normal', 2_300],
    ['fast', 950],
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

    vi.advanceTimersByTime(2_300);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    queue.setSpeed('fast');
    vi.advanceTimersByTime(2_299);
    expect(queue.current()?.type).toBe('BOT_TRANSFER');
    vi.advanceTimersByTime(1);
    expect(queue.current()?.type).toBe('BOT_DEFEND');
    vi.advanceTimersByTime(950);
    expect(queue.locked()).toBe(false);
    expect(seen).toEqual(['BOT_INITIAL_ATTACK', 'BOT_TRANSFER', 'BOT_DEFEND']);
  });
});
