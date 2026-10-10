import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { DeckConfigSelectorComponent } from './deck-config-selector';

describe('DeckConfigSelectorComponent', () => {
  beforeEach(() => {
    localStorage.setItem('kiba.preferred-locale', 'en');
    TestBed.configureTestingModule({
      imports: [DeckConfigSelectorComponent],
      providers: [provideRouter([])],
    });
  });

  it.each([
    ['classic', 1, '36 cards total'],
    ['extended', 1, '54 cards total'],
    ['classic', 2, '72 cards total'],
    ['extended', 2, '108 cards total'],
  ] as const)('shows the derived total for %s x%s', async (profile, deckCount, total) => {
    const fixture = TestBed.createComponent(DeckConfigSelectorComponent);
    fixture.componentRef.setInput('profile', profile);
    fixture.componentRef.setInput('deckCount', deckCount);
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(total);
  });

  it('uses labeled native radios and emits independent profile and count choices', async () => {
    const fixture = TestBed.createComponent(DeckConfigSelectorComponent);
    fixture.componentRef.setInput('profile', 'classic');
    fixture.componentRef.setInput('deckCount', 1);
    fixture.componentRef.setInput('playerCount', 4);
    const profile = vi.spyOn(fixture.componentInstance.profileChange, 'emit');
    const deckCount = vi.spyOn(fixture.componentInstance.deckCountChange, 'emit');
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('fieldset')).toHaveLength(2);
    expect(element.querySelectorAll('input[name="deckProfile"]')).toHaveLength(2);
    expect(element.querySelectorAll('input[name="deckCount"]')).toHaveLength(2);
    expect(element.textContent).toContain('Recommended for 3–4 players');

    element.querySelector<HTMLInputElement>('input[value="extended"]')!.click();
    element.querySelector<HTMLInputElement>('input[name="deckCount"][value="2"]')!.click();
    expect(profile).toHaveBeenCalledWith('extended');
    expect(deckCount).toHaveBeenCalledWith(2);
  });
});
