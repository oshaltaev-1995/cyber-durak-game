import { PvPCredentialStore } from './pvp-credential.store';

describe('PvPCredentialStore', () => {
  beforeEach(() => sessionStorage.clear());

  it.each(['three', 'four'] as const)('restores the same multiplayer seat %s', (seat) => {
    const store = new PvPCredentialStore();
    const credential = {
      participant_id: `participant-${seat}`,
      seat,
      reconnect_token: 'private-token',
    };

    store.save('ABC123', credential);

    expect(store.get('ABC123')).toEqual(credential);
  });
});
