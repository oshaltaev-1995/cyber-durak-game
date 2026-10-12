import { TestBed } from '@angular/core/testing';
import { BotSpeedControlComponent } from './bot-speed-control';

describe('BotSpeedControlComponent', () => {
  it('exposes an accessible segmented radio group and emits a changed pace', async () => {
    const fixture = TestBed.createComponent(BotSpeedControlComponent);
    fixture.componentRef.setInput('speed', 'normal');
    const emitted = vi.fn();
    fixture.componentInstance.speedChange.subscribe(emitted);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    const radios = element.querySelectorAll<HTMLInputElement>('input[type="radio"]');
    expect(radios).toHaveLength(3);
    expect(element.querySelector('legend')?.textContent).toContain('Темп ботов');
    expect(radios[1].checked).toBe(true);
    radios[0].dispatchEvent(new Event('change'));
    expect(emitted).toHaveBeenCalledWith('fast');
  });
});
