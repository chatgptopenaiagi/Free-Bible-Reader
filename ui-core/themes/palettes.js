export const COLOR_FIELDS = Object.freeze(['primary','secondary','accent','background','surface','text','muted','border','selected','control','link','highlight','graphSelection','crossReference']);

const classic = {primary:'#24445d',secondary:'#655c50',accent:'#80601e',background:'#faf9f6',surface:'#ffffff',text:'#202a32',muted:'#596570',border:'#b9c2ca',selected:'#dae9f4',control:'#e9eef2',link:'#15558f',highlight:'#fff0ad',graphSelection:'#a3440c',crossReference:'#425a99'};
function palette(id,label,changes) { return Object.freeze({id,label,colors:Object.freeze({...classic,...changes})}); }
export const PALETTES = Object.freeze([
  palette('classicBible','Classic Bible',{}),
  palette('modernBlue','Modern Blue',{primary:'#164c81',secondary:'#476078',accent:'#00657a',background:'#f5f9fd',selected:'#d5e9fc',link:'#00579e',graphSelection:'#005e9b',crossReference:'#514596'}),
  palette('forestGreen','Forest Green',{primary:'#23523d',secondary:'#566546',accent:'#765b12',background:'#f6f9f4',selected:'#d9eadc',link:'#246143',graphSelection:'#2d6b40',crossReference:'#4a5d84'}),
  palette('royalPurple','Royal Purple',{primary:'#553372',secondary:'#665270',accent:'#825c17',background:'#faf7fc',selected:'#e8ddf1',link:'#653a92',graphSelection:'#6c3c90',crossReference:'#394e92'}),
  palette('warmParchment','Warm Parchment',{primary:'#62482b',secondary:'#6d5a3e',accent:'#745213',background:'#f6eddb',surface:'#fff9ec',text:'#352b21',muted:'#655642',border:'#b9a88d',selected:'#e6d8b8',control:'#ecdfc7',link:'#6d401b',highlight:'#f5dd92',graphSelection:'#855012',crossReference:'#675186'}),
  palette('monochrome','Monochrome',{primary:'#333333',secondary:'#555555',accent:'#444444',background:'#fafafa',surface:'#ffffff',text:'#151515',muted:'#565656',border:'#a8a8a8',selected:'#dedede',control:'#eeeeee',link:'#333333',highlight:'#e5e5e5',graphSelection:'#222222',crossReference:'#4b4b4b'}),
  palette('userCustom','User Custom',{}),
]);
export const THEME_MODES = Object.freeze(['light','dark','system','sepia','contrast','custom']);
export function normalizeColor(value) {
  if (typeof value !== 'string' || !/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) return null;
  let hex=value.slice(1).toLowerCase();
  if(hex.length===3) hex=[...hex].map(char=>char+char).join('');
  return '#'+hex;
}
