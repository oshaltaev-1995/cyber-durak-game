import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { MatchHistoryResponse } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';
import { HistoryPageComponent } from './history-page';

const user = {
  id: 'user-1',
  email: 'player@example.com',
  display_name: 'Игрок',
  created_at: '2026-08-27T10:00:00+00:00',
};

const populated: MatchHistoryResponse = {
  items: [
    {
      id: 'match-1',
      outcome: 'WIN',
      opponent_type: 'PVP',
      opponent_display_name: 'Alice',
      started_at: '2026-08-27T10:00:00+00:00',
      completed_at: '2026-08-27T10:04:18+00:00',
      duration_seconds: 258,
      initial_attacker: 'YOU',
      final_human_card_count: 0,
      final_bot_card_count: 3,
      human_action_count: 14,
      human_transfer_count: 2,
      human_take_count: 1,
      human_throw_in_count: 4,
      max_transfer_target: 72,
      arithmetic_mean_throw_in_count: 1,
    },
    {
      id: 'match-2',
      outcome: 'DRAW',
      opponent_type: 'BOT',
      opponent_display_name: null,
      started_at: '2026-08-26T10:00:00+00:00',
      completed_at: '2026-08-26T10:02:00+00:00',
      duration_seconds: 120,
      initial_attacker: 'BOT',
      final_human_card_count: 0,
      final_bot_card_count: 0,
      human_action_count: 8,
      human_transfer_count: 0,
      human_take_count: 0,
      human_throw_in_count: 1,
      max_transfer_target: 0,
      arithmetic_mean_throw_in_count: 0,
    },
    {
      id: 'match-3',
      outcome: 'LOSS',
      opponent_type: 'BOT',
      opponent_display_name: null,
      started_at: '2026-08-25T10:00:00+00:00',
      completed_at: '2026-08-25T10:03:00+00:00',
      duration_seconds: 180,
      initial_attacker: 'BOT',
      final_human_card_count: 2,
      final_bot_card_count: 0,
      human_action_count: 9,
      human_transfer_count: 1,
      human_take_count: 2,
      human_throw_in_count: 0,
      max_transfer_target: 18,
      arithmetic_mean_throw_in_count: 0,
    },
  ],
  total: 3,
  limit: 20,
  offset: 0,
};

describe('HistoryPageComponent', () => {
  const currentUser = signal<typeof user | null>(user);
  const profile = { getMatches: vi.fn(() => of(populated)) };

  beforeEach(() => {
    currentUser.set(user);
    profile.getMatches.mockReturnValue(of(populated));
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { currentUser, refresh: vi.fn(() => of(currentUser())) },
        },
        { provide: ProfileService, useValue: profile },
      ],
    });
  });

  it('renders mobile-friendly win and draw history cards', () => {
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelectorAll('.match-card')).toHaveLength(3);
    expect(element.textContent).toContain('Победа');
    expect(element.textContent).toContain('Поражение');
    expect(element.textContent).toContain('Ничья');
    expect(element.textContent).toContain('4 мин 18 сек');
    expect(element.textContent).toContain('Макс. перевод');
    expect(element.textContent).toContain('против Alice');
    expect(element.textContent).toContain('против бота');
  });

  it('filters history by PvP without changing pagination semantics', () => {
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();
    const pvp = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'PvP',
    ) as HTMLButtonElement;

    pvp.click();

    expect(profile.getMatches).toHaveBeenLastCalledWith(20, 0, 'PVP');
  });

  it('renders the authenticated empty state', () => {
    profile.getMatches.mockReturnValue(of({ items: [], total: 0, limit: 20, offset: 0 }));
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Пока нет сыгранных партий',
    );
  });

  it('uses an anonymized label when a deleted PvP opponent has no snapshot', () => {
    profile.getMatches.mockReturnValue(
      of({
        ...populated,
        items: [{ ...populated.items[0], opponent_display_name: null }],
        total: 1,
      }),
    );
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('против Удалённый игрок');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Alice');
  });

  it('does not request private history for a guest', () => {
    currentUser.set(null);
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'История доступна после входа',
    );
  });

  it('shows a private-history loading error', () => {
    profile.getMatches.mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(HistoryPageComponent);
    fixture.detectChanges();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent,
    ).toContain('Не удалось загрузить историю');
  });
});
