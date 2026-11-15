/** Interface-language identities. Scripture editions and parser locales are separate. */
export const DEFAULT_LANGUAGE = 'en';
export const LANGUAGES = Object.freeze([
  Object.freeze({ id: 'en', code: 'en', locale: 'en', nativeName: 'English', labelKey: 'languages.en', direction: 'ltr', catalog: 'en.json', enabled: true }),
  Object.freeze({ id: 'ro', code: 'ro', locale: 'ro', nativeName: 'Română', labelKey: 'languages.ro', direction: 'ltr', catalog: 'ro.json', enabled: true }),
  Object.freeze({ id: 'de', code: 'de', locale: 'de', nativeName: 'Deutsch', labelKey: 'languages.de', direction: 'ltr', catalog: 'de.json', enabled: true }),
]);
export const SUPPORTED_LANGUAGES = Object.freeze(LANGUAGES.map(language => language.code));
export const LANGUAGE_REGISTRY = Object.freeze(Object.fromEntries(LANGUAGES.map(language => [language.code, language])));
export function resolveLanguage(input) {
  const requested = typeof input === 'string' ? input.trim() : '';
  const primary = requested.toLowerCase().replaceAll('_', '-').split('-')[0];
  const supported = Object.hasOwn(LANGUAGE_REGISTRY, primary);
  return { requested, language: supported ? primary : DEFAULT_LANGUAGE, supported, fallback: !supported };
}
export function normalizeLanguage(input) { return resolveLanguage(input).language; }
export function getLanguageDescriptor(input) { return LANGUAGE_REGISTRY[normalizeLanguage(input)]; }
export const availableLanguages = LANGUAGES;
export default LANGUAGES;
