import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import { Achievement } from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';
import { AchievementsPageComponent } from './achievements-page';

const user = {
  id: 'user-1',
  email: 'player@example.com',
  display_name: 'Игрок',
  created_at: '2026-08-27T10:00:00+00:00',
};

const achievements: readonly Achievement[] = [
  {
    code: 'FIRST_MATCH',
    title: 'Первая партия',
    description: 'Сыграть первую партию.',
    bonus_xp: 25,
    unlocked: true,
    unlocked_at: '2026-08-27T10:04:00+00:00',
  },
  {
    code: 'TEN_WINS',
    title: 'Победитель',
    description: 'Выиграть 10 партий.',
    bonus_xp: 150,
    unlocked: false,
    unlocked_at: null,
  },
];

describe('AchievementsPageComponent', () => {
  const currentUser = signal<typeof user | null>(user);
  const profile = { getAchievements: vi.fn(() => of(achievements)) };

  beforeEach(() => {
    currentUser.set(user);
    profile.getAchievements.mockReturnValue(of(achievements));
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

  it('renders unlocked and locked catalogue entries with XP and date', () => {
    const fixture = TestBed.createComponent(AchievementsPageComponent);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelectorAll('.achievement')).toHaveLength(2);
    expect(element.querySelectorAll('.achievement.unlocked')).toHaveLength(1);
    expect(element.textContent).toContain('Первая партия');
    expect(element.textContent).toContain('+25 XP');
    expect(element.textContent).toContain('Получено');
    expect(element.textContent).toContain('Пока не получено');
    expect(element.textContent).toContain('+150 XP');
  });

  it('does not request private achievements for a guest', () => {
    currentUser.set(null);
    profile.getAchievements.mockClear();
    const fixture = TestBed.createComponent(AchievementsPageComponent);
    fixture.detectChanges();

    expect(profile.getAchievements).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Достижения доступны после входа',
    );
  });

  it('renders an API error without hiding navigation', () => {
    profile.getAchievements.mockReturnValue(throwError(() => new Error('offline')));
    const fixture = TestBed.createComponent(AchievementsPageComponent);
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Не удалось загрузить достижения');
    expect(text).toContain('История');
  });
});
