import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';

const user = {
  id: 'user-1',
  email: 'player@example.com',
  display_name: 'Игрок',
  created_at: '2026-08-27T10:00:00+00:00',
};

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AuthService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the current account and treats 401 as guest state', () => {
    service.refresh().subscribe();
    http.expectOne('/api/auth/me').flush(user);
    expect(service.currentUser()).toEqual(user);

    service.refresh().subscribe((value) => expect(value).toBeNull());
    http.expectOne('/api/auth/me').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(service.currentUser()).toBeNull();
    expect(service.initialized()).toBe(true);
  });

  it('registers and logs in without storing a token in frontend state', () => {
    service
      .register({ email: user.email, display_name: user.display_name, password: 'password123' })
      .subscribe();
    const registration = http.expectOne('/api/auth/register');
    expect(registration.request.body).toEqual({
      email: user.email,
      display_name: user.display_name,
      password: 'password123',
    });
    registration.flush(user);
    expect(service.currentUser()).toEqual(user);

    service.login({ email: user.email, password: 'password123' }).subscribe();
    const login = http.expectOne('/api/auth/login');
    expect(login.request.body).toEqual({ email: user.email, password: 'password123' });
    login.flush(user);
    expect(JSON.stringify(service.currentUser())).not.toContain('token');
  });

  it('updates the profile and logs out', () => {
    service.updateDisplayName('Новое имя').subscribe();
    const update = http.expectOne('/api/profile');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body).toEqual({ display_name: 'Новое имя' });
    update.flush({ ...user, display_name: 'Новое имя' });
    expect(service.currentUser()?.display_name).toBe('Новое имя');

    service.logout().subscribe();
    const logout = http.expectOne('/api/auth/logout');
    expect(logout.request.method).toBe('POST');
    expect(logout.request.body).toBeNull();
    logout.flush(null);
    expect(service.currentUser()).toBeNull();
  });
});
