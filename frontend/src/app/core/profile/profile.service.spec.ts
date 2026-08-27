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
});
