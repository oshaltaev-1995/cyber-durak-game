import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { App } from './app';
import { GameApiService } from './core/api/game-api.service';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [{ provide: GameApiService, useValue: { createGame: () => of(null) } }],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the playable Kiba landing screen', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand')?.textContent).toContain('KIBA');
    expect(compiled.querySelector('h1')?.textContent).toContain('KIBA');
    expect(compiled.querySelector('button')?.textContent).toContain('Играть');
  });
});
