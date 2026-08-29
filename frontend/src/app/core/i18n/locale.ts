export const SUPPORTED_LOCALES = ['ru', 'en'] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const KIBA_LOCALE_STORAGE_KEY = 'kiba.preferred-locale';

export function parseLocale(value: string | null | undefined): Locale {
  return value?.toLowerCase().startsWith('ru') ? 'ru' : 'en';
}

export function isLocale(value: string | null): value is Locale {
  return value === 'ru' || value === 'en';
}
