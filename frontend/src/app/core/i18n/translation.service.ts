import { DOCUMENT } from '@angular/common';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { isLocale, KIBA_LOCALE_STORAGE_KEY, Locale } from './locale';
import { en } from './translations/en';
import { ru, TranslationKey } from './translations/ru';

type TranslationParams = Readonly<Record<string, string | number>>;
type CardCountForm = 'one' | 'few' | 'many';

const CARD_COUNT_KEYS: Readonly<Record<CardCountForm, TranslationKey>> = {
  one: 'common.cards.one',
  few: 'common.cards.few',
  many: 'common.cards.many',
};

const TAKE_CARD_COUNT_KEYS: Readonly<Record<CardCountForm, TranslationKey>> = {
  one: 'common.cards.take.one',
  few: 'common.cards.take.few',
  many: 'common.cards.take.many',
};

@Injectable({ providedIn: 'root' })
export class TranslationService {
  private readonly document = inject(DOCUMENT);
  private readonly title = inject(Title);
  private readonly selected = signal<Locale>(this.initialLocale());

  readonly locale = this.selected.asReadonly();
  readonly isEnglish = computed(() => this.selected() === 'en');

  constructor() {
    this.applyDocumentLanguage(this.selected());
  }

  t(key: TranslationKey, params: TranslationParams = {}): string {
    let value = (this.selected() === 'ru' ? ru : en)[key];
    for (const [name, replacement] of Object.entries(params)) {
      value = value.replaceAll(`{${name}}`, String(replacement));
    }
    return value;
  }

  setLocale(locale: Locale): void {
    this.selected.set(locale);
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, locale);
    this.applyDocumentLanguage(locale);
  }

  useAccountLocale(locale: Locale): void {
    this.setLocale(locale);
  }

  setTitle(key: TranslationKey = 'meta.default'): void {
    this.title.setTitle(this.t(key));
  }

  cardCount(count: number): string {
    return this.t(CARD_COUNT_KEYS[this.cardCountForm(count)]);
  }

  takeCardCount(count: number): string {
    return this.t(TAKE_CARD_COUNT_KEYS[this.cardCountForm(count)]);
  }

  private cardCountForm(count: number): CardCountForm {
    if (this.selected() === 'en') return count === 1 ? 'one' : 'many';
    const mod10 = count % 10;
    const mod100 = count % 100;
    if (mod10 === 1 && mod100 !== 11) return 'one';
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
      return 'few';
    }
    return 'many';
  }

  formatDate(value: string, options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }): string {
    return new Intl.DateTimeFormat(this.selected() === 'ru' ? 'ru-RU' : 'en-US', options).format(
      new Date(value),
    );
  }

  formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
    return new Intl.NumberFormat(this.selected() === 'ru' ? 'ru-RU' : 'en-US', options).format(
      value,
    );
  }

  private initialLocale(): Locale {
    const stored = localStorage.getItem(KIBA_LOCALE_STORAGE_KEY);
    if (isLocale(stored)) return stored;
    const locale: Locale = 'en';
    localStorage.setItem(KIBA_LOCALE_STORAGE_KEY, locale);
    return locale;
  }

  private applyDocumentLanguage(locale: Locale): void {
    this.document.documentElement.lang = locale;
  }
}
