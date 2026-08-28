import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ProfileService } from './profile.service';

describe('ProfileService', () => {
  let service: ProfileService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ProfileService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProfileService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads account statistics', () => {
    service.getStatistics().subscribe();
    const request = http.expectOne('/api/stats');
    expect(request.request.method).toBe('GET');
    request.flush({ games_played: 0 });
  });

  it('loads paginated private match history', () => {
    service.getMatches(10, 20).subscribe();
    const request = http.expectOne('/api/matches?limit=10&offset=20');
    expect(request.request.method).toBe('GET');
    request.flush({ items: [], total: 0, limit: 10, offset: 20 });
  });

  it('filters private match history by opponent type', () => {
    service.getMatches(20, 0, 'PVP').subscribe();
    const request = http.expectOne('/api/matches?limit=20&offset=0&opponent_type=PVP');
    expect(request.request.method).toBe('GET');
    request.flush({ items: [], total: 0, limit: 20, offset: 0 });
  });

  it('loads derived progression', () => {
    service.getProgression().subscribe();
    const request = http.expectOne('/api/progression');
    expect(request.request.method).toBe('GET');
    request.flush({ total_xp: 0, level: 1 });
  });

  it('loads the authoritative achievement catalogue', () => {
    service.getAchievements().subscribe();
    const request = http.expectOne('/api/achievements');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('loads cosmetic catalogue and updates the current loadout', () => {
    service.getCosmetics().subscribe();
    const request = http.expectOne('/api/cosmetics');
    expect(request.request.method).toBe('GET');
    request.flush({
      items: [],
      loadout: {
        card_back_code: 'LEVEL_3_BACK',
        table_theme_code: 'NIGHT_TABLE',
        profile_frame_code: 'LEVEL_2_FRAME',
      },
    });
    expect(service.currentLoadout().table_theme_code).toBe('NIGHT_TABLE');
  });

  it('equips a cosmetic and retains server-confirmed loadout', () => {
    service.equipCosmetics({ card_back_code: 'SNOWBALL_BACK' }).subscribe();
    const request = http.expectOne('/api/profile/cosmetics');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ card_back_code: 'SNOWBALL_BACK' });
    request.flush({
      items: [],
      loadout: {
        card_back_code: 'SNOWBALL_BACK',
        table_theme_code: 'CLASSIC_TABLE',
        profile_frame_code: 'NO_FRAME',
      },
    });
    expect(service.currentLoadout().card_back_code).toBe('SNOWBALL_BACK');
  });
});
