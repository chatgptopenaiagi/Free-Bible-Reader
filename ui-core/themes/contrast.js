function rgb(value){return[1,3,5].map(index=>parseInt(value.slice(index,index+2),16)/255);}
export function luminance(color){return rgb(color).map(value=>value<=0.04045?value/12.92:((value+0.055)/1.055)**2.4).reduce((sum,value,index)=>sum+value*[0.2126,0.7152,0.0722][index],0);}
export function contrastRatio(a,b){const values=[luminance(a),luminance(b)].sort((x,y)=>y-x);return(values[0]+0.05)/(values[1]+0.05);}
export function contrastingText(background){return contrastRatio('#000000',background)>=contrastRatio('#ffffff',background)?'#000000':'#ffffff';}
export function contrastReport(colors,target=4.5) {
  const pairs=[['text','background'],['text','surface'],['muted','surface'],['link','surface'],['crossReference','surface'],['primary','background'],['secondary','background'],['accent','background']].map(([foreground,background])=>{const ratio=contrastRatio(colors[foreground],colors[background]);return{foreground,background,ratio,required:target,pass:ratio>=target};});
  return {target,pairs,warnings:pairs.filter(pair=>!pair.pass).map(pair=>({...pair,code:'LOW_CONTRAST'})),passes:pairs.every(pair=>pair.pass)};
}
export function suggestColor(colors,foreground='text',background='background',target=4.5) {
  if(!Object.hasOwn(colors,foreground)||!Object.hasOwn(colors,background))throw new TypeError('UNKNOWN_COLOR_FIELD');
  if(typeof target!=='number'||!Number.isFinite(target)||target<1||target>21)throw new RangeError('INVALID_CONTRAST_TARGET');
  const suggested=contrastingText(colors[background]),ratio=contrastRatio(suggested,colors[background]);
  return {field:foreground,current:colors[foreground],backgroundField:background,suggested,ratio,target,passes:ratio>=target,wouldChangePreference:false};
}
