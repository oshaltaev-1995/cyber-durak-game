import { TestBed } from '@angular/core/testing';
import { FirstRunStore, KIBA_FIRST_RUN_SEEN_KEY } from './first-run.store';

describe('FirstRunStore', () => {
  let store: FirstRunStore;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    store = TestBed.inject(FirstRunStore);
  });

  it('stores only a minimal first-run preference', () => {
    expect(store.hasSeenWelcome()).toBe(false);

    store.markWelcomeSeen();

    expect(store.hasSeenWelcome()).toBe(true);
    expect(Object.keys(localStorage)).toEqual([KIBA_FIRST_RUN_SEEN_KEY]);
    expect(localStorage.getItem(KIBA_FIRST_RUN_SEEN_KEY)).toBe('true');
  });
});
