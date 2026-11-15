import {bcv_parser} from './vendor/esm/bcv_parser.js';
import * as en from './vendor/esm/lang/en.js';
import * as ro from './vendor/esm/lang/ro.js';
import * as de from './vendor/esm/lang/de.js';
import * as ar from './vendor/esm/lang/ar.js';
import {createInterface} from 'node:readline';

const languages={en,ro,de,ar};
function collect(node,invalid,alternates,messages) {
  if(!node || typeof node!=='object')return;
  if(node.valid?.valid===false)invalid.push(node.valid.messages??{});
  if(node.valid?.messages&&Object.keys(node.valid.messages).length)messages.push(node.valid.messages);
  if(Array.isArray(node.alternates))alternates.push(...node.alternates);
  for(const [key,val] of Object.entries(node))if(key!=='alternates') {
    if(Array.isArray(val))for(const child of val)collect(child,invalid,alternates,messages);
    else if(val && typeof val==='object')collect(val,invalid,alternates,messages);
  }
}
export function parseReference(request) {
  const language=request.language??'en';
  const input=String(request.reference??'');
  if(!languages[language])return {status:'UNSUPPORTED_LANGUAGE',language,normalized:[],osis:'',input:request.reference};
  const p=new bcv_parser(languages[language]);
  p.set_options({osis_compaction_strategy:'bcv',versification_system:'kjv',testaments:request.apocrypha?'ona':'on',
    invalid_passage_strategy:'include',invalid_sequence_strategy:'include',book_alone_strategy:'full',
    punctuation_strategy:['de','ro'].includes(language)&&/\d\s*,\s*\d/.test(input)?'eu':'us',zero_chapter_strategy:'error',zero_verse_strategy:'error'});
  if(request.operation==='metadata')return {status:'VALID',language,version:'4.0.0',reference_system:'openbibleinfo-kjv',metadata:p.translation_info('kjv')};
  if(input.length>1000)return {status:'INVALID',input,normalized:[],osis:'',errors:['Input exceeds1000characters']};
  p.parse(input);const entities=p.parsed_entities(),invalid=[],alternates=[],messages=[];collect(entities,invalid,alternates,messages);
  const osis=p.osis(), normalized=osis?osis.split(','):[];
  const corrections=messages.filter(m=>Object.keys(m).some(k=>/not_exist|is_zero|less_than/.test(k)));
  const shortened=/\b(\d+)\s*[:.]\s*(\d+)\s*[-–]\s*(\d+)(?![\d:.])/.exec(input);
  const shortenedAmbiguous=shortened&&Number(shortened[3])<Number(shortened[2]);
  const status=invalid.length||corrections.length?'INVALID':alternates.length||shortenedAmbiguous?'AMBIGUOUS':normalized.length?'VALID':'UNRECOGNIZED';
  return {status,input,language,osis,normalized,reference_system:'openbibleinfo-kjv',parser_version:'4.0.0',
    invalid_messages:invalid,validation_messages:messages,corrections_rejected:corrections,
    abbreviated_endpoint_requires_confirmation:!!shortenedAmbiguous,alternates,indices:p.osis_and_indices(),entities,
    note:'Reference normalization is not edition equivalence or theological equivalence.'};
}
const io=createInterface({input:process.stdin,crlfDelay:Infinity});
for await(const line of io) {
  if(!line.trim())continue;
  try{process.stdout.write(JSON.stringify(parseReference(JSON.parse(line)))+'\n');}
  catch(error){process.stdout.write(JSON.stringify({status:'ERROR',error:String(error.message),normalized:[]})+'\n');}
}
