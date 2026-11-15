import { DEFAULT_LANGUAGE, LANGUAGE_REGISTRY, resolveLanguage } from './registry.js';
import { validateCatalog } from './validation.js';

const ALLOWED_ATTRIBUTES = new Set(['aria-label', 'aria-description', 'aria-valuetext', 'title', 'placeholder', 'alt']);
const DIRECT_ATTRIBUTES = ['aria-label', 'aria-description', 'aria-valuetext', 'title', 'placeholder', 'alt'];
async function fetchCatalog(language) {
  const response = await fetch(new URL(LANGUAGE_REGISTRY[language].catalog, import.meta.url));
  if (!response.ok) throw new Error(`Catalog request failed (${response.status})`);
  return response.json();
}

/** Plain-text localization only. Optional injected loader/logger support isolated tests. */
export async function createTranslator(initialLanguage = DEFAULT_LANGUAGE, { loader = fetchCatalog, logger = globalThis.console, onWarning = null } = {}) {
  const cache = new Map();
  const listeners = new Set();
  const warnings = [];
  const warned = new Set();
  let language = DEFAULT_LANGUAGE;
  let latestRequest = 0;
  function warn(code, details = {}) {
    const warning = Object.freeze({ code, language, ...details });
    const identity = `${code}:${warning.language}:${warning.key ?? ''}:${warning.requested ?? ''}`;
    if (warned.has(identity)) return;
    warned.add(identity); warnings.push(warning);
    try { logger?.warn?.('[FREE BIBLE READER i18n]', warning); } catch { /* Logging cannot break the reader. */ }
    try { onWarning?.(warning); } catch { /* A diagnostic subscriber cannot break localization. */ }
  }
  async function load(code) {
    if (!cache.has(code)) cache.set(code, Promise.resolve().then(() => loader(code)).then(value => {
      const report = validateCatalog(value, { language: code });
      if (!report.valid) { const error = new Error('Invalid plain-text interface catalog'); error.report = report; throw error; }
      return Object.freeze(Object.assign(Object.create(null), value));
    }).catch(error => { cache.delete(code); throw error; }));
    return cache.get(code);
  }
  const english = await load(DEFAULT_LANGUAGE);
  let catalog = english;
  function t(key, params = {}) {
    if (typeof key !== 'string' || !key) { warn('I18N_INVALID_KEY'); return '⟦invalid-key⟧'; }
    let message;
    if (Object.hasOwn(catalog, key)) message = catalog[key];
    else if (Object.hasOwn(english, key)) { warn('I18N_MISSING_KEY', { key, fallback: DEFAULT_LANGUAGE }); message = english[key]; }
    else { warn('I18N_UNKNOWN_KEY', { key }); return `⟦${key}⟧`; }
    const values = params && typeof params === 'object' ? params : {};
    return message.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (original, name) => {
      if (!Object.hasOwn(values, name) || values[name] === undefined || values[name] === null) { warn('I18N_MISSING_PARAM', { key, parameter: name }); return original; }
      return String(values[name]);
    });
  }
  async function setLanguage(requested) {
    const sequence = ++latestRequest;
    const selection = resolveLanguage(requested);
    if (!selection.supported) warn('I18N_UNSUPPORTED_LANGUAGE', { requested: selection.requested, fallback: DEFAULT_LANGUAGE });
    let next = selection.language;
    let loaded;
    let fallback = selection.fallback;
    try { loaded = await load(next); }
    catch { warn('I18N_LOAD_FAILED', { requested: next, fallback: DEFAULT_LANGUAGE }); next = DEFAULT_LANGUAGE; loaded = english; fallback = true; }
    if (sequence !== latestRequest) return language; // Last explicit selection wins a slow fetch race.
    const previousLanguage = language;
    language = next; catalog = loaded;
    const change = Object.freeze({ language, previousLanguage, requested: selection.requested, fallback, locale: LANGUAGE_REGISTRY[language].locale, direction: LANGUAGE_REGISTRY[language].direction });
    for (const listener of [...listeners]) {
      try { listener(change); } catch { warn('I18N_SUBSCRIBER_ERROR'); }
    }
    return language;
  }
  function subscribe(listener) {
    if (typeof listener !== 'function') throw new TypeError('Translation subscriber must be a function');
    listeners.add(listener);
    return () => listeners.delete(listener);
  }
  function formatNumber(value, options = {}) {
    if (!(typeof value === 'bigint' || typeof value === 'number' && Number.isFinite(value))) { warn('I18N_INVALID_NUMBER'); return '—'; }
    try { return new Intl.NumberFormat(LANGUAGE_REGISTRY[language].locale, options).format(value); }
    catch { warn('I18N_FORMAT_ERROR'); return String(value); }
  }
  function localize(root = globalThis.document) {
    const result = { language, textNodes: 0, attributes: 0, skipped: 0 };
    if (!root || typeof root.querySelectorAll !== 'function') return result;
    if (root.nodeType === 9 && root.documentElement) {
      root.documentElement.setAttribute('lang', language);
      root.documentElement.setAttribute('dir', LANGUAGE_REGISTRY[language].direction);
    }
    const selector = '[data-i18n],[data-i18n-attr],' + DIRECT_ATTRIBUTES.map(attribute => `[data-i18n-${attribute}]`).join(',');
    const elements = [...(root.matches?.(selector) ? [root] : []), ...root.querySelectorAll(selector)];
    for (const element of elements) {
      if (element.closest?.('[data-i18n-ignore],[data-source-data]')) { result.skipped++; continue; }
      let params = {};
      const encoded = element.getAttribute('data-i18n-params');
      if (encoded) {
        try { params = JSON.parse(encoded); if (!params || typeof params !== 'object' || Array.isArray(params)) throw new Error('Expected parameters object'); }
        catch { warn('I18N_INVALID_PARAMS', { key: element.getAttribute('data-i18n') ?? '' }); params = {}; }
      }
      const key = element.getAttribute('data-i18n');
      if (key) { element.textContent = t(key, params); result.textNodes++; }
      const attributes = [];
      for (const attribute of DIRECT_ATTRIBUTES) {
        const attributeKey = element.getAttribute(`data-i18n-${attribute}`);
        if (attributeKey) attributes.push([attribute, attributeKey]);
      }
      const declarations = element.getAttribute('data-i18n-attr');
      if (declarations) for (const item of declarations.split(';')) {
        const colon = item.indexOf(':');
        if (colon > 0) attributes.push([item.slice(0, colon).trim(), item.slice(colon + 1).trim()]);
      }
      for (const [attribute, attributeKey] of attributes) {
        if (!ALLOWED_ATTRIBUTES.has(attribute)) { warn('I18N_UNSAFE_ATTRIBUTE', { key: attributeKey, attribute }); continue; }
        element.setAttribute(attribute, t(attributeKey, params)); result.attributes++;
      }
    }
    return result;
  }
  const api = { t, setLanguage, formatNumber, subscribe, localize,
    has: key => typeof key === 'string' && (Object.hasOwn(catalog, key) || Object.hasOwn(english, key)),
    getWarnings: () => [...warnings],
    get language() { return language; }, get locale() { return LANGUAGE_REGISTRY[language].locale; },
    get direction() { return LANGUAGE_REGISTRY[language].direction; } };
  await setLanguage(initialLanguage);
  return api;
}
export default createTranslator;
