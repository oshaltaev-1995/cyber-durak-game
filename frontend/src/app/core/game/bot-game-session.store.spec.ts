import { TestBed } from '@angular/core/testing';
import { BotGameSessionStore } from './bot-game-session.store';

describe('BotGameSessionStore', () => {
  let store: BotGameSessionStore;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [BotGameSessionStore] });
    store = TestBed.inject(BotGameSessionStore);
  });

  it('stores only the active bot game identifier for the tab session', () => {
    store.save(' game-42 ');

    expect(store.get()).toBe('game-42');
    expect(Object.keys(sessionStorage)).toEqual(['kiba.activeBotGameId']);
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBe('game-42');
  });

  it('clears the active bot game identifier', () => {
    store.save('game-42');
    store.clear();

    expect(store.get()).toBeNull();
  });

  it('removes empty stored identifiers', () => {
    sessionStorage.setItem('kiba.activeBotGameId', '   ');

    expect(store.get()).toBeNull();
    expect(sessionStorage.getItem('kiba.activeBotGameId')).toBeNull();
  });
});
