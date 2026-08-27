import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { PvPApiService } from './pvp-api.service';
import { PvPRoomJoin, PvPRoomStatus } from './pvp.models';

describe('PvPApiService', () => {
  let service: PvPApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PvPApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a guest room without putting credentials in the URL', () => {
    const response = { invite_code: 'ABC123' } as PvPRoomJoin;
    service.createRoom('Alice').subscribe((value) => expect(value).toBe(response));
    const request = http.expectOne('/api/pvp/rooms');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ nickname: 'Alice' });
    request.flush(response);
  });

  it('loads public room status', () => {
    const response = { invite_code: 'ABC123' } as PvPRoomStatus;
    service.getRoom('ABC123').subscribe((value) => expect(value).toBe(response));
    const request = http.expectOne('/api/pvp/rooms/ABC123');
    expect(request.request.method).toBe('GET');
    request.flush(response);
  });

  it('joins an authenticated player without a duplicate nickname', () => {
    service.joinRoom('ABC123', null).subscribe();
    const request = http.expectOne('/api/pvp/rooms/ABC123/join');
    expect(request.request.body).toEqual({ nickname: null });
    request.flush({});
  });
});
