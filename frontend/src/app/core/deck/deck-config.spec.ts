import { cardIdentity, deckCardCount, isDefaultDeckConfig } from './deck-config';

describe('deck configuration presentation helpers', () => {
  it.each([
    ['classic', 1, 36],
    ['extended', 1, 54],
    ['classic', 2, 72],
    ['extended', 2, 108],
  ] as const)('derives %s × %i as %i physical cards', (profile, copies, total) => {
    expect(deckCardCount(profile, copies)).toBe(total);
  });

  it('treats only Single Classic as profile-counted default', () => {
    expect(isDefaultDeckConfig({ deck_profile: 'classic', deck_count: 1 })).toBe(true);
    expect(isDefaultDeckConfig({ deck_profile: 'extended', deck_count: 1 })).toBe(false);
    expect(isDefaultDeckConfig({ deck_profile: 'classic', deck_count: 2 })).toBe(false);
  });

  it('uses physical identity while preserving the unique-face legacy fallback', () => {
    expect(cardIdentity({ id: 'deck-2:KH', code: 'KH' })).toBe('deck-2:KH');
    expect(cardIdentity({ code: 'KH' })).toBe('KH');
  });
});
