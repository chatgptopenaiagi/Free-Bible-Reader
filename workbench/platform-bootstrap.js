/* Restore app preferences before importing any UI modules. Android's random
 * loopback port deliberately changes each launch; SharedPreferences owns state.
 * The native bridge exists only in the trusted, session-protected WebView. */
(() => {
  if (!globalThis.FBRNative?.invoke) return;
  try { globalThis.FBRPlatform = JSON.parse(FBRNative.invoke('app.info', '{}')); } catch {}
  const read = operation => JSON.parse(FBRNative.invoke(operation, '{}'));
  try {
    const saved = read('preferences.load');
    if (saved.status === 'ERROR') throw new Error(saved.message);
    for (const [key, value] of Object.entries(saved.values || {})) {
      if (typeof value === 'string' && key.length < 250 && value.length < 500000)
        localStorage.setItem(key, value);
    }
    let timer;
    const persist = () => {
      clearTimeout(timer);
      const values = {};
      for (let index = 0; index < localStorage.length; index++) {
        const key = localStorage.key(index);
        values[key] = localStorage.getItem(key);
      }
      const result = JSON.parse(FBRNative.invoke('preferences.save', JSON.stringify({values})));
      if (result.status === 'ERROR') console.warn('Preferences persistence unavailable');
    };
    for (const name of ['setItem', 'removeItem', 'clear']) {
      const original = Storage.prototype[name];
      Storage.prototype[name] = function (...args) {
        const result = original.apply(this, args);
        if (this === localStorage) { clearTimeout(timer); timer = setTimeout(persist, 100); }
        return result;
      };
    }
    addEventListener('pagehide', persist);
    document.addEventListener('visibilitychange', () => { if (document.hidden) persist(); });
    document.documentElement.dataset.platform = 'android';
  } catch (error) {
    // Reading remains available when a device's preference store is unavailable.
    console.warn('Saved Android preferences could not be restored', error.name);
  }
})();
