import {createPreferences}from './preferences/store.js';
import {createTheme}from './themes/theme.js';
import {createTypography}from './typography/typography.js';
import {createCapabilities}from './platform/capabilities.js';
export {PALETTES,COLOR_FIELDS,THEME_MODES}from './themes/palettes.js';
export {FONT_OPTIONS}from './typography/fonts.js';
export {DEFAULT_PREFERENCES,PREFERENCES_VERSION,STORAGE_KEY,READING_WIDTHS,WORKSPACE_LAYOUTS,DENSITIES,CONTRAST_PREFERENCES}from './preferences/schema.js';
export {contrastRatio}from './themes/contrast.js';
export {SAFETY_TOKENS}from './tokens/index.js';
export function createUICore(options={}) {
  const win=options.window??globalThis.window;
  const root=options.root??win?.document?.documentElement??globalThis.document?.documentElement;
  const preferences=createPreferences({...options,window:win});
  const theme=createTheme({preferences,root,window:win});
  const typography=createTypography({preferences,root,window:win});
  const capabilities=createCapabilities({window:win,root,preferences});
  return Object.freeze({preferences,theme,typography,capabilities,destroy(){theme.destroy();typography.destroy();preferences.destroy();}});
}
