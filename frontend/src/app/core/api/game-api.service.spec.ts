import { provideHttpClient } from '@angular/common/http';
import { HttpErrorResponse } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { GameResponse } from './game-api.models';
import { GameApiService } from './game-api.service';

const response = { game_id: 'game-1' } as GameResponse;

describe('GameApiService', () => {
  let service: GameApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [GameApiService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(GameApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a game', () => {
    service.createGame().subscribe((game) => expect(game).toBe(response));
    const request = http.expectOne('/api/games');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toBeNull();
    request.flush(response);
  });

  it('gets a game', () => {
    service.getGame('game-1').subscribe((game) => expect(game).toBe(response));
    const request = http.expectOne('/api/games/game-1');
    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('requests private read-only hints for the current selection', () => {
    service.getHints('game-1', ['9C', '9D']).subscribe();
    const request = http.expectOne('/api/games/game-1/hints');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ selected_card_ids: ['9C', '9D'] });
    request.flush({
      selected_card_ids: ['9C', '9D'],
      suggested_card_ids: [],
      suggested_action_types: ['INITIAL_ATTACK'],
      combinations: [],
    });
  });

  it('submits card actions with canonical card codes', () => {
    service
      .submitAction('game-1', 'DEFEND', ['QS', '6C'])
      .subscribe((game) => expect(game).toBe(response));
    const request = http.expectOne('/api/games/game-1/actions');
    expect(request.request.body).toEqual({ action: 'DEFEND', cards: ['QS', '6C'] });
    request.flush(response);
  });

  it.each(['TAKE', 'BITO'] as const)('submits %s without card data', (action) => {
    service.submitAction('game-1', action).subscribe();
    const request = http.expectOne('/api/games/game-1/actions');
    expect(request.request.body).toEqual({ action });
    request.flush(response);
  });

  it('propagates API errors', () => {
    let received: HttpErrorResponse | undefined;
    service.submitAction('game-1', 'TAKE').subscribe({
      error: (error: HttpErrorResponse) => (received = error),
    });
    http
      .expectOne('/api/games/game-1/actions')
      .flush({ detail: { code: 'not_human_turn' } }, { status: 409, statusText: 'Conflict' });
    expect(received?.status).toBe(409);
  });
});
