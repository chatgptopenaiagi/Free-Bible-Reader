/** Dependency-free structural/parity checks for plain-text interface catalogs. */
export function extractPlaceholders(value) {
  return [...new Set(typeof value === 'string' ? [...value.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)].map(match => match[1]) : [])].sort();
}
export function validateCatalog(catalog, { language = 'unknown', baseCatalog = null, requiredKeys = [] } = {}) {
  const errors = [];
  if (!catalog || typeof catalog !== 'object' || Array.isArray(catalog)) {
    return { valid: false, language, keyCount: 0, errors: [{ code: 'INVALID_CATALOG', language }] };
  }
  const keys = Object.keys(catalog).sort();
  for (const key of keys) {
    if (!/^[A-Za-z0-9_.-]+$/.test(key) || ['__proto__', 'constructor', 'prototype'].includes(key)) errors.push({ code: 'INVALID_KEY', language, key });
    if (typeof catalog[key] !== 'string' || !catalog[key].trim()) errors.push({ code: 'INVALID_MESSAGE', language, key });
    else if (/<\/?[A-Za-z!][^>]*>/.test(catalog[key])) errors.push({ code: 'HTML_MESSAGE_UNSUPPORTED', language, key });
  }
  for (const key of requiredKeys) if (!Object.hasOwn(catalog, key)) errors.push({ code: 'MISSING_REQUIRED_KEY', language, key });
  if (baseCatalog) {
    for (const key of Object.keys(baseCatalog)) {
      if (!Object.hasOwn(catalog, key)) errors.push({ code: 'MISSING_KEY', language, key });
      else if (JSON.stringify(extractPlaceholders(catalog[key])) !== JSON.stringify(extractPlaceholders(baseCatalog[key]))) errors.push({ code: 'PLACEHOLDER_MISMATCH', language, key });
    }
    for (const key of keys) if (!Object.hasOwn(baseCatalog, key)) errors.push({ code: 'EXTRA_KEY', language, key });
  }
  return { valid: errors.length === 0, language, keyCount: keys.length, keys, errors };
}
export function validateCatalogs(catalogs, { baseLanguage = 'en', requiredKeys = [] } = {}) {
  if (!catalogs || !Object.hasOwn(catalogs, baseLanguage)) return { valid: false, status: 'FAIL', errors: [{ code: 'MISSING_BASE_CATALOG', language: baseLanguage }], catalogs: {} };
  const reports = Object.fromEntries(Object.entries(catalogs).map(([language, catalog]) => [language, validateCatalog(catalog, { language, baseCatalog: language === baseLanguage ? null : catalogs[baseLanguage], requiredKeys })]));
  const errors = Object.values(reports).flatMap(report => report.errors);
  return { valid: errors.length === 0, status: errors.length ? 'FAIL' : 'PASS', baseLanguage, keyCount: Object.keys(catalogs[baseLanguage]).length, errors, catalogs: reports };
}
export function assertCatalogs(catalogs, options) {
  const report = validateCatalogs(catalogs, options);
  if (!report.valid) { const error = new Error('Interface catalog validation failed'); error.report = report; throw error; }
  return report;
}
export default validateCatalogs;
