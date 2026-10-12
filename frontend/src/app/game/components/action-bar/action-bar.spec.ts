import { TestBed } from '@angular/core/testing';
import { GameCard } from '../../../core/api/game-api.models';
import { TranslationService } from '../../../core/i18n/translation.service';
import { ActionBarComponent } from './action-bar';

const cards = (count: number): readonly GameCard[] =>
  Array.from({ length: count }, (_, index) => ({
    id: `deck-${index < 5 ? 1 : 2}:${index}`,
    code: `${(index % 9) + 2}C`,
    rank: String((index % 9) + 2),
    suit: 'clubs',
    base_value: (index % 9) + 2,
    effective_value: (index % 9) + 2,
    is_trump: false,
  }));

describe('ActionBarComponent', () => {
  it.each([
    ['en', 'BITO'],
    ['ru', 'Бито'],
  ] as const)('presents native two-player BITO in %s', async (locale, label) => {
    TestBed.inject(TranslationService).setLocale(locale);
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['BITO']);
    fixture.componentRef.setInput('selectedCards', []);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.textContent?.trim()).toBe(label);
  });

  it.each([
    ['en', 'Pass'],
    ['ru', 'Пас'],
  ] as const)('presents multiplayer BITO protocol intent as %s Pass', async (locale, label) => {
    TestBed.inject(TranslationService).setLocale(locale);
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['BITO']);
    fixture.componentRef.setInput('selectedCards', []);
    fixture.componentRef.setInput('bitoAsPass', true);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.textContent?.trim()).toBe(label);
  });

  it('blocks an exact transfer that exceeds the next defender cap with a specific explanation', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['TRANSFER']);
    fixture.componentRef.setInput('selectedCards', [
      { ...cards(1)[0], effective_value: 12 },
      { ...cards(1)[0], id: 'two', effective_value: 14 },
      { ...cards(1)[0], id: 'three', effective_value: 14 },
    ]);
    fixture.componentRef.setInput('activeAttackValue', 40);
    fixture.componentRef.setInput('totalAttackCardCount', 4);
    fixture.componentRef.setInput('nextDefenderHandCount', 5);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'После перевода будет 7 атакующих карт',
    );
  });

  it('allows an exact transfer when both value and new-defender cap fit', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['TRANSFER']);
    fixture.componentRef.setInput('selectedCards', [
      { ...cards(1)[0], effective_value: 20 },
      { ...cards(1)[0], id: 'two', effective_value: 20 },
    ]);
    fixture.componentRef.setInput('activeAttackValue', 40);
    fixture.componentRef.setInput('totalAttackCardCount', 4);
    fixture.componentRef.setInput('nextDefenderHandCount', 7);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'совпадает с целью перевода',
    );
  });

  it('rejects a transfer whose sum does not match any canonical transfer basis', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['TRANSFER']);
    fixture.componentRef.setInput('selectedCards', cards(2));
    fixture.componentRef.setInput('activeAttackValue', 40);
    fixture.componentRef.setInput('totalAttackCardCount', 1);
    fixture.componentRef.setInput('nextDefenderHandCount', 7);
    await fixture.whenStable();

    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Для перевода нужно ровно 40',
    );
  });

  it('accepts a same-rank extended transfer with an exact target subset', async () => {
    const seven = (id: string, value: number): GameCard => ({
      id,
      code: '7H',
      rank: '7',
      suit: 'hearts',
      base_value: value === 14 ? 7 : value,
      effective_value: value,
      is_trump: value === 14,
    });
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['TRANSFER']);
    fixture.componentRef.setInput('selectedCards', [
      seven('selected-1', 14),
      seven('selected-2', 7),
      seven('selected-3', 14),
    ]);
    fixture.componentRef.setInput('activeAttackCards', [seven('attack', 7)]);
    fixture.componentRef.setInput('activeAttackValue', 21);
    fixture.componentRef.setInput('totalAttackCardCount', 1);
    fixture.componentRef.setInput('nextDefenderHandCount', 7);
    await fixture.whenStable();

    expect(
      (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.actions button')!
        .disabled,
    ).toBe(false);
  });

  it('does not expose Transfer after the authoritative transfer window closes', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['DEFEND', 'TAKE']);
    fixture.componentRef.setInput('selectedCards', []);
    fixture.componentRef.setInput('activeAttackValue', 20);
    await fixture.whenStable();

    const labels = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].map(
      (button) => button.textContent?.trim(),
    );
    expect(labels).not.toContain('Перевести');
  });

  it('uses the authoritative addition cap instead of a fixed seven-card UI limit', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['INITIAL_ATTACK']);
    fixture.componentRef.setInput('selectedCards', cards(10));
    fixture.componentRef.setInput('maxAttackCardAddition', 10);
    await fixture.whenStable();

    let button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Выбрано: 10');

    fixture.componentRef.setInput('selectedCards', cards(11));
    fixture.detectChanges();
    button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(true);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('остаток лимита атаки 10');
  });

  it('uses exact authoritative legality for submission without restricting card selection', async () => {
    const fixture = TestBed.createComponent(ActionBarComponent);
    fixture.componentRef.setInput('actions', ['INITIAL_ATTACK']);
    fixture.componentRef.setInput('selectedCards', cards(3));
    fixture.componentRef.setInput('legalActionTypes', []);
    await fixture.whenStable();

    let button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(true);

    fixture.componentRef.setInput('selectedCards', cards(5));
    fixture.componentRef.setInput('legalActionTypes', ['INITIAL_ATTACK']);
    fixture.detectChanges();
    button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>(
      '.actions button',
    )!;
    expect(button.disabled).toBe(false);
  });
});
