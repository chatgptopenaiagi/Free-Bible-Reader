import {COLOR_FIELDS,PALETTES,THEME_MODES,normalizeColor} from '../themes/palettes.js';
import {FONT_OPTIONS} from '../typography/fonts.js';
export const PREFERENCES_VERSION=2;
export const PREFERENCES_FORMAT='biblia-ui-preferences';
export const STORAGE_KEY='biblia.ui.preferences.v2';
export const READING_WIDTHS=Object.freeze(['narrow','comfortable','wide']);
export const WORKSPACE_LAYOUTS=Object.freeze(['single','dual','triple','research','reading']);
export const DENSITIES=Object.freeze(['comfortable','compact','spacious']);
export const CONTRAST_PREFERENCES=Object.freeze(['standard','more']);
export const DEFAULT_PREFERENCES=Object.freeze({
  themeMode:'light',colorPalette:'classicBible',customColors:Object.freeze({}),interfaceLanguage:'en',
  interfaceFont:'segoeUI',scriptureFont:'georgia',interfaceFontScale:1,scriptureFontScale:1.2,
  lineHeight:1.7,paragraphSpacing:1,readingWidth:'comfortable',workspaceLayout:'reading',
  panelVisibility:Object.freeze({reader:true,research:true,inspector:true,sidebar:true}),
  panelCollapsed:Object.freeze({reader:false,research:false,inspector:false,sidebar:false}),
  panelSizes:Object.freeze({reader:55,research:30,inspector:15,sidebar:20}),
  displayDensity:'comfortable',reducedMotion:false,contrastPreference:'standard',
});
export const clone=value=>JSON.parse(JSON.stringify(value));
export function plain(value) {return value!==null && typeof value==='object' && !Array.isArray(value) && (Object.getPrototypeOf(value)===Object.prototype || Object.getPrototypeOf(value)===null);}
const ENUMS={themeMode:THEME_MODES,colorPalette:PALETTES.map(item=>item.id),interfaceLanguage:['en','ro','de'],interfaceFont:FONT_OPTIONS.map(item=>item.id),scriptureFont:FONT_OPTIONS.map(item=>item.id),readingWidth:READING_WIDTHS,workspaceLayout:WORKSPACE_LAYOUTS,displayDensity:DENSITIES,contrastPreference:CONTRAST_PREFERENCES};
const RANGES={interfaceFontScale:[0.8,1.6],scriptureFontScale:[0.8,2.5],lineHeight:[1.2,2.4],paragraphSpacing:[0.25,2.5]};
const FORBIDDEN=new Set(['__proto__','constructor','prototype']);
export function validatePreferences(patch,base=DEFAULT_PREFERENCES,{replace=false}={}) {
  const state=clone(replace?DEFAULT_PREFERENCES:base),diagnostics=[];
  const issue=(field,code)=>diagnostics.push({field,code});
  if(!plain(patch))return {state,diagnostics:[{field:'preferences',code:'INVALID_TYPE'}]};
  for(const [key,value] of Object.entries(patch)) {
    if(!Object.hasOwn(DEFAULT_PREFERENCES,key)){issue(key,'UNKNOWN_KEY');continue;}
    if(ENUMS[key]){if(ENUMS[key].includes(value))state[key]=value;else issue(key,'INVALID_ENUM');continue;}
    if(RANGES[key]){const [min,max]=RANGES[key];if(typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max)state[key]=value;else issue(key,'OUT_OF_RANGE');continue;}
    if(key==='reducedMotion'){if(typeof value==='boolean')state[key]=value;else issue(key,'INVALID_TYPE');continue;}
    if(!plain(value)){issue(key,'INVALID_TYPE');continue;}
    const map=key==='customColors'&&Object.keys(value).length===0?{}:clone(state[key]);
    for(const [field,entry]of Object.entries(value)) {
      if(key==='customColors') {
        const color=normalizeColor(entry);
        if(!COLOR_FIELDS.includes(field)){issue(key+'.'+field,'UNKNOWN_KEY');continue;}
        if(color===null){issue(key+'.'+field,'INVALID_COLOR');continue;}
        map[field]=color;
      } else {
        if(!/^[a-z][a-z0-9_-]{0,31}$/.test(field)||FORBIDDEN.has(field)){issue(key+'.'+field,'UNKNOWN_KEY');continue;}
        if(!Object.hasOwn(map,field)&&Object.keys(map).length>=32){issue(key+'.'+field,'OUT_OF_RANGE');continue;}
        if(key==='panelSizes') {
          if(typeof entry!=='number'||!Number.isFinite(entry)||entry<1||entry>4096){issue(key+'.'+field,'OUT_OF_RANGE');continue;}
        }else if(typeof entry!=='boolean'){issue(key+'.'+field,'INVALID_TYPE');continue;}
        map[field]=entry;
      }
    }
    state[key]=map;
  }
  return {state,diagnostics};
}
export function decodePreferences(text) {
  if(typeof text!=='string'||text.length>65536)throw new TypeError('INVALID_JSON');
  let raw;try{raw=JSON.parse(text);}catch{throw new SyntaxError('INVALID_JSON');}
  if(!plain(raw))throw new TypeError('INVALID_TYPE');
  let version=0,prefs=raw;
  if(Object.hasOwn(raw,'version')) {
    if(!Number.isInteger(raw.version)||raw.version<0||raw.version>PREFERENCES_VERSION)throw new RangeError('UNSUPPORTED_VERSION');
    version=raw.version;
    if(raw.format!==undefined&&raw.format!==PREFERENCES_FORMAT)throw new TypeError('INVALID_TYPE');
    prefs=raw.preferences??raw.prefs;
  }
  if(!plain(prefs))throw new TypeError('INVALID_TYPE');
  if(version<2) {
    prefs={...prefs};
    const aliases={theme:'themeMode',palette:'colorPalette',language:'interfaceLanguage',font:'scriptureFont',fontScale:'scriptureFontScale'};
    for(const [oldName,newName]of Object.entries(aliases))if(Object.hasOwn(prefs,oldName)){if(!Object.hasOwn(prefs,newName))prefs[newName]=prefs[oldName];delete prefs[oldName];}
    if(Object.hasOwn(prefs,'fontSize')){if(!Object.hasOwn(prefs,'interfaceFontScale')&&typeof prefs.fontSize==='number')prefs.interfaceFontScale=prefs.fontSize/16;delete prefs.fontSize;}
  }
  return {...validatePreferences(prefs,DEFAULT_PREFERENCES,{replace:true}),sourceVersion:version,migrated:version<PREFERENCES_VERSION};
}
export function encodePreferences(state){return JSON.stringify({format:PREFERENCES_FORMAT,version:PREFERENCES_VERSION,preferences:state},null,2);}
