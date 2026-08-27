import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { PvPApiService } from '../core/pvp/pvp-api.service';
import { PvPCredentialStore } from '../core/pvp/pvp-credential.store';
import { PvPRoomJoin } from '../core/pvp/pvp.models';
import { PvPLobbyPageComponent } from './pvp-lobby-page';

describe('PvPLobbyPageComponent', () => {
  let fixture: ComponentFixture<PvPLobbyPageComponent>;
  const api = { createRoom: vi.fn() };
  const credentials = { save: vi.fn() };
  const currentUser = signal<{ display_name: string } | null>(null);

  beforeEach(async () => {
    api.createRoom.mockReset();
    credentials.save.mockReset();
    currentUser.set(null);
    await TestBed.configureTestingModule({
      imports: [PvPLobbyPageComponent],
      providers: [
        provideRouter([]),
        { provide: PvPApiService, useValue: api },
        { provide: PvPCredentialStore, useValue: credentials },
        { provide: AuthService, useValue: { currentUser } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(PvPLobbyPageComponent);
    fixture.detectChanges();
  });

  it('offers guest nickname creation and manual invite entry', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Ваше имя');
    expect(text).toContain('Создать комнату');
    expect(text).toContain('Войти по коду');
  });

  it('stores the reconnect credential and navigates without putting it in the URL', async () => {
    const response = {
      invite_code: 'ABC123',
      credential: { participant_id: 'p1', seat: 'one', reconnect_token: 'top-secret' },
    } as PvPRoomJoin;
    api.createRoom.mockReturnValue(of(response));
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const input = (fixture.nativeElement as HTMLElement).querySelector(
      'input[autocomplete="nickname"]',
    ) as HTMLInputElement;
    input.value = 'Alice';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const button = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (value) => value.textContent?.includes('Создать комнату'),
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();

    expect(api.createRoom).toHaveBeenCalledWith('Alice');
    expect(credentials.save).toHaveBeenCalledWith('ABC123', response.credential);
    expect(navigate).toHaveBeenCalledWith(['/pvp/room', 'ABC123']);
    expect(JSON.stringify(navigate.mock.calls)).not.toContain('top-secret');
  });

  it('uses authenticated identity without sending a nickname override', () => {
    currentUser.set({ display_name: 'Account Alice' });
    fixture.detectChanges();
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    api.createRoom.mockReturnValue(
      of({
        invite_code: 'AccountRoom',
        credential: { participant_id: 'p1', seat: 'one', reconnect_token: 'secret' },
      } as PvPRoomJoin),
    );

    const button = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (value) => value.textContent?.includes('Создать комнату'),
    ) as HTMLButtonElement;
    button.click();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Account Alice');
    expect(api.createRoom).toHaveBeenCalledWith(null);
  });
});
