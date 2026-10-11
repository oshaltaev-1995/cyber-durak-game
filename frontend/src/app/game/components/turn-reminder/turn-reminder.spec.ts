import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TURN_REMINDER_DELAY_MS, TurnReminderComponent } from './turn-reminder';

describe('TurnReminderComponent', () => {
  let fixture: ComponentFixture<TurnReminderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [TurnReminderComponent] }).compileComponents();
  });

  afterEach(() => vi.useRealTimers());

  it('shows one non-blocking reminder after thirty seconds without emitting gameplay', () => {
    vi.useFakeTimers();
    fixture = TestBed.createComponent(TurnReminderComponent);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('.turn-perimeter')).not.toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).toBeNull();
    expect((fixture.nativeElement as HTMLElement).classList).not.toContain('attention');

    vi.advanceTimersByTime(TURN_REMINDER_DELAY_MS - 1);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).toBeNull();

    vi.advanceTimersByTime(1);
    fixture.detectChanges();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')?.textContent,
    ).toContain('Ваш ход');
    expect((fixture.nativeElement as HTMLElement).classList).toContain('attention');

    vi.advanceTimersByTime(TURN_REMINDER_DELAY_MS * 2);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelectorAll('.turn-reminder')).toHaveLength(
      1,
    );
  });

  it('clears attention immediately when the local decision context changes', () => {
    vi.useFakeTimers();
    fixture = TestBed.createComponent(TurnReminderComponent);
    fixture.componentRef.setInput('contextKey', 'bout:one');
    fixture.detectChanges();
    vi.advanceTimersByTime(TURN_REMINDER_DELAY_MS);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).classList).toContain('attention');

    fixture.componentRef.setInput('contextKey', 'bout:two');
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).classList).not.toContain('attention');
    expect((fixture.nativeElement as HTMLElement).querySelector('.turn-reminder')).toBeNull();
    expect(vi.getTimerCount()).toBe(1);
  });

  it('cancels the reminder when the decision component is destroyed', () => {
    vi.useFakeTimers();
    fixture = TestBed.createComponent(TurnReminderComponent);
    fixture.detectChanges();
    fixture.destroy();

    expect(() => vi.advanceTimersByTime(TURN_REMINDER_DELAY_MS)).not.toThrow();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('keeps an accessible static waiting description for reduced-motion users', () => {
    vi.useFakeTimers();
    const original = window.matchMedia;
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockReturnValue({ matches: true }),
    });
    try {
      fixture = TestBed.createComponent(TurnReminderComponent);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).textContent).toContain(
        'Напоминание о ходе — автоматического тайм-аута нет',
      );
      vi.advanceTimersByTime(TURN_REMINDER_DELAY_MS);
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ваш ход');
      expect((fixture.nativeElement as HTMLElement).classList).toContain('attention');
    } finally {
      Object.defineProperty(window, 'matchMedia', { configurable: true, value: original });
    }
  });
});
