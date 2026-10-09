import { TestBed } from '@angular/core/testing';
import {
  KIBA_MULTIPLAYER_ONBOARDING_KEY,
  MultiplayerOnboardingStore,
} from './multiplayer-onboarding.store';

describe('MultiplayerOnboardingStore', () => {
  let store: MultiplayerOnboardingStore;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    store = TestBed.inject(MultiplayerOnboardingStore);
  });

  it('stores only the versioned local onboarding preference', () => {
    expect(store.hasSeen()).toBe(false);
    store.markSeen();
    expect(store.hasSeen()).toBe(true);
    expect(Object.keys(localStorage)).toEqual([KIBA_MULTIPLAYER_ONBOARDING_KEY]);
  });
});
