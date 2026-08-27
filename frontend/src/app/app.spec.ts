import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { App } from './app';
import { routes } from './app.routes';
import { GameApiService } from './core/api/game-api.service';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter(routes),
        { provide: GameApiService, useValue: { createGame: () => of(null) } },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('renders the compact product shell and landing choices', async () => {
    const fixture = TestBed.createComponent(App);
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand')?.textContent).toContain('KIBA');
    expect(compiled.querySelector('h1')?.textContent).toContain('KIBA');
    expect(compiled.textContent).toContain('Карточная игра с арифметикой');
    expect(compiled.querySelector('a[href="/play"]')?.textContent).toContain('Играть');
    expect(compiled.querySelector('a[href="/tutorial"]')?.textContent).toContain('Обучение');
    expect(compiled.querySelector('a[href="/rules"]')?.textContent).toContain('Правила');
  });

  it('routes to tutorial and rules without starting a gameplay API call', async () => {
    const createGame = vi.fn(() => of(null));
    TestBed.overrideProvider(GameApiService, { useValue: { createGame } });
    const fixture = TestBed.createComponent(App);
    const router = TestBed.inject(Router);

    await router.navigateByUrl('/tutorial');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Цель и карты');

    await router.navigateByUrl('/rules');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Правила игры');
    expect(createGame).not.toHaveBeenCalled();
  });
});
