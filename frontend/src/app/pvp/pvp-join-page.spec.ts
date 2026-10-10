import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPRoomJoin, PvPRoomStatus } from '../core/pvp/pvp.models';
import { PvPJoinPageComponent } from './pvp-join-page';

const waitingRoom: PvPRoomStatus = {
  invite_code: 'MixedCase',
  room_phase: 'WAITING_FOR_OPPONENT',
  version: 0,
  capacity: 2,
  deck_profile: 'classic',
  deck_count: 1,
  joined_count: 1,
  participants: [
    {
      participant_id: 'p1',
      seat: 'one',
      display_name: 'Alice',
      connected: true,
      authenticated: false,
    },
  ],
};

describe('PvPJoinPageComponent', () => {
  let fixture: ComponentFixture<PvPJoinPageComponent>;
  const api = { getRoom: vi.fn(), joinRoom: vi.fn() };
  const credentials = { get: vi.fn(), save: vi.fn() };
  const currentUser = signal<{ display_name: string } | null>(null);

  async function create(): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [PvPJoinPageComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ inviteCode: 'MixedCase' }) } },
        },
        { provide: PvPApiService, useValue: api },
        { provide: PvPCredentialStore, useValue: credentials },
        { provide: AuthService, useValue: { currentUser } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(PvPJoinPageComponent);
    fixture.detectChanges();
  }

  beforeEach(() => {
    api.getRoom.mockReset();
    api.joinRoom.mockReset();
    credentials.get.mockReset().mockReturnValue(null);
    credentials.save.mockReset();
    currentUser.set(null);
  });

  it('loads joinable status and joins a guest without changing case-sensitive code', async () => {
    api.getRoom.mockReturnValue(of(waitingRoom));
    const response = {
      invite_code: 'MixedCase',
      credential: { participant_id: 'p2', seat: 'two', reconnect_token: 'secret' },
    } as PvPRoomJoin;
    api.joinRoom.mockReturnValue(of(response));
    await create();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Комната от Alice');
    const input = (fixture.nativeElement as HTMLElement).querySelector(
      'input[autocomplete="nickname"]',
    ) as HTMLInputElement;
    input.value = 'Bob';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const button = (fixture.nativeElement as HTMLElement).querySelector(
      'button.primary',
    ) as HTMLButtonElement;
    button.click();

    expect(api.joinRoom).toHaveBeenCalledWith('MixedCase', 'Bob');
    expect(credentials.save).toHaveBeenCalledWith('MixedCase', response.credential);
    expect(navigate).toHaveBeenCalledWith(['/pvp/room', 'MixedCase']);
  });

  it('uses account identity without requesting a guest nickname', async () => {
    currentUser.set({ display_name: 'Account Bob' });
    api.getRoom.mockReturnValue(of(waitingRoom));
    api.joinRoom.mockReturnValue(
      of({
        invite_code: 'MixedCase',
        credential: { participant_id: 'p2', seat: 'two', reconnect_token: 'secret' },
      } as PvPRoomJoin),
    );
    await create();
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Account Bob');
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('input[autocomplete="nickname"]'),
    ).toBeNull();
    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('button.primary')
      ?.click();
    expect(api.joinRoom).toHaveBeenCalledWith('MixedCase', null);
  });

  it('shows remaining capacity for a joinable multiplayer room', async () => {
    api.getRoom.mockReturnValue(of({ ...waitingRoom, capacity: 4, joined_count: 2 }));
    await create();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'В комнате 2 из 4 игроков',
    );
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Комната на 4 игроков');
    expect((fixture.nativeElement as HTMLElement).querySelector('button.primary')).not.toBeNull();
  });

  it('shows an immutable double-deck room configuration and progression policy to joiners', async () => {
    api.getRoom.mockReturnValue(
      of({ ...waitingRoom, capacity: 4, deck_profile: 'extended', deck_count: 2 }),
    );
    await create();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Расширенная · 2 колоды · 108 карт');
    expect(element.textContent).toContain('Варианты колоды пока не влияют');
    expect(element.querySelector('input[name="deckProfile"]')).toBeNull();
    expect(element.querySelector('input[name="deckCount"]')).toBeNull();
  });

  it('shows a full room without a join action', async () => {
    api.getRoom.mockReturnValue(of({ ...waitingRoom, room_phase: 'GAME_ACTIVE' }));
    await create();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Комната уже заполнена');
    expect((fixture.nativeElement as HTMLElement).querySelector('button.primary')).toBeNull();
  });

  it('shows expired or missing rooms as unavailable', async () => {
    api.getRoom.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 404, error: { detail: 'not found' } })),
    );
    await create();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Комната недоступна');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Комната не найдена или уже закрыта.',
    );
  });
});
