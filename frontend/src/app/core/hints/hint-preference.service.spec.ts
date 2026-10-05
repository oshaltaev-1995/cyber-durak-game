import { TestBed } from '@angular/core/testing';
import { HintPreferenceService, KIBA_HINTS_ENABLED_KEY } from './hint-preference.service';

describe('HintPreferenceService', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
  });

  it('defaults hints on when no preference has been saved', () => {
    expect(TestBed.inject(HintPreferenceService).enabled()).toBe(true);
  });

  it('persists off and on immediately', () => {
    const service = TestBed.inject(HintPreferenceService);
    service.setEnabled(false);
    expect(service.enabled()).toBe(false);
    expect(localStorage.getItem(KIBA_HINTS_ENABLED_KEY)).toBe('false');
    service.setEnabled(true);
    expect(localStorage.getItem(KIBA_HINTS_ENABLED_KEY)).toBe('true');
  });

  it('restores an off preference in a fresh service instance', () => {
    localStorage.setItem(KIBA_HINTS_ENABLED_KEY, 'false');
    expect(new HintPreferenceService().enabled()).toBe(false);
  });
});
