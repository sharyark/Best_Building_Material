import { en, type TextKey } from './en'

export type { TextKey }

const dictionaries: Record<string, Partial<Record<TextKey, string>>> = { en }
let locale = 'en'

export function setLocale(next: string) {
  locale = dictionaries[next] ? next : 'en'
  document.documentElement.lang = locale
  document.documentElement.dir = ['ur', 'ar'].includes(locale) ? 'rtl' : 'ltr'
}

export function t(key: TextKey): string {
  return dictionaries[locale]?.[key] ?? en[key]
}

export function useT() {
  return t
}
