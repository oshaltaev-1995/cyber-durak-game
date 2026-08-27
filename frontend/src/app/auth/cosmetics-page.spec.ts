import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../core/auth/auth.service';
import {
  CosmeticEquipRequest,
  CosmeticsResponse,
  DEFAULT_COSMETIC_LOADOUT,
} from '../core/profile/profile.models';
import { ProfileService } from '../core/profile/profile.service';
import { CosmeticsPageComponent } from './cosmetics-page';

const user = {
  id: 'user-1',
  email: 'player@example.com',
  display_name: 'Игрок',
  created_at: '2026-08-27T10:00:00+00:00',
};

const catalogue: CosmeticsResponse = {
  loadout: DEFAULT_COSMETIC_LOADOUT,
  items: [
    {
      code: 'CLASSIC',
      category: 'CARD_BACK',
      title: 'Классика',
      description: 'Стандартная рубашка Kiba.',
      unlocked: true,
      equipped: true,
      unlock: { type: 'DEFAULT', requirement: null, achievement_title: null },
      unlocked_at: null,
    },
    {
      code: 'SNOWBALL_BACK',
      category: 'CARD_BACK',
      title: 'Снежный ком',
      description: 'Награда за большой перевод.',
      unlocked: true,
      equipped: false,
      unlock: {
        type: 'ACHIEVEMENT',
        requirement: 'SNOWBALL_36',
        achievement_title: 'Снежный ком',
      },
      unlocked_at: '2026-08-27T10:00:00+00:00',
    },
    {
      code: 'NIGHT_TABLE',
      category: 'TABLE_THEME',
      title: 'Ночной стол',
      description: 'Более тёмный вариант игрового стола.',
      unlocked: false,
      equipped: false,
      unlock: { type: 'LEVEL', requirement: 4, achievement_title: null },
      unlocked_at: null,
    },
    {
      code: 'NO_FRAME',
      category: 'PROFILE_FRAME',
      title: 'Без рамки',
      description: 'Чистое оформление профиля.',
      unlocked: true,
      equipped: true,
      unlock: { type: 'DEFAULT', requirement: null, achievement_title: null },
      unlocked_at: null,
    },
  ],
};

interface ProfileStub {
  getCosmetics: ReturnType<typeof vi.fn<() => Observable<CosmeticsResponse>>>;
  equipCosmetics: ReturnType<
    typeof vi.fn<(request: CosmeticEquipRequest) => Observable<CosmeticsResponse>>
  >;
}

describe('CosmeticsPageComponent', () => {
  let fixture: ComponentFixture<CosmeticsPageComponent>;
  let profile: ProfileStub;
  const currentUser = signal<typeof user | null>(user);

  beforeEach(() => {
    currentUser.set(user);
    profile = {
      getCosmetics: vi.fn(() => of(catalogue)),
      equipCosmetics: vi.fn(() => of(catalogue)),
    };
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

  function create(): HTMLElement {
    fixture = TestBed.createComponent(CosmeticsPageComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('groups previews and renders unlocked, locked, and equipped states', () => {
    const element = create();

    expect(element.textContent).toContain('Рубашки');
    expect(element.textContent).toContain('Столы');
    expect(element.textContent).toContain('Рамки');
    expect(element.querySelectorAll('.card-back-preview')).toHaveLength(2);
    expect(element.querySelectorAll('.table-preview')).toHaveLength(1);
    expect(element.querySelectorAll('.frame-preview')).toHaveLength(1);
    expect(element.querySelectorAll('.cosmetic-card.locked')).toHaveLength(1);
    expect(element.querySelectorAll('.cosmetic-card.equipped')).toHaveLength(2);
    expect(element.textContent).toContain('Откроется на уровне 4');
    expect(element.textContent).toContain('Нужно достижение «Снежный ком»');
    expect(element.textContent).toContain('Выбрано');
    expect(element.textContent).toContain('Закрыто');
  });

  it('equips an unlocked card back through the server API', () => {
    const updated: CosmeticsResponse = {
      ...catalogue,
      loadout: { ...DEFAULT_COSMETIC_LOADOUT, card_back_code: 'SNOWBALL_BACK' },
      items: catalogue.items.map((item) => ({
        ...item,
        equipped: item.code === 'SNOWBALL_BACK' || item.code === 'NO_FRAME',
      })),
    };
    profile.equipCosmetics.mockReturnValue(of(updated));
    const element = create();
    const snowball = [...element.querySelectorAll('.cosmetic-card')].find((card) =>
      card.textContent?.includes('Снежный ком'),
    );
    (snowball?.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(profile.equipCosmetics).toHaveBeenCalledWith({ card_back_code: 'SNOWBALL_BACK' });
    expect(snowball?.textContent).toContain('Выбрано');
  });

  it('does not call equip for a locked item', () => {
    const element = create();
    const night = [...element.querySelectorAll('.cosmetic-card')].find((card) =>
      card.textContent?.includes('Ночной стол'),
    );
    const button = night?.querySelector('button') as HTMLButtonElement;

    expect(button.disabled).toBe(true);
    button.click();
    expect(profile.equipCosmetics).not.toHaveBeenCalled();
  });

  it('keeps catalogue visible when the equip API rejects a stale unlock', () => {
    profile.equipCosmetics.mockReturnValue(
      throwError(() => new HttpErrorResponse({ status: 409 })),
    );
    const element = create();
    const snowball = [...element.querySelectorAll('.cosmetic-card')].find((card) =>
      card.textContent?.includes('Снежный ком'),
    );
    (snowball?.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(element.querySelector('[role="alert"]')?.textContent).toContain('пока недоступно');
    expect(element.textContent).toContain('Классика');
  });

  it('does not request persistent cosmetics for a guest', () => {
    currentUser.set(null);
    profile.getCosmetics.mockClear();
    const element = create();

    expect(profile.getCosmetics).not.toHaveBeenCalled();
    expect(element.textContent).toContain('Гости всегда играют с классическим видом');
  });
});
