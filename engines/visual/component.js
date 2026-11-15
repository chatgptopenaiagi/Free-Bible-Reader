/** Bounded arc adapter for the BIBLIA lab, not the upstream all-link WebGL application.
 * Source geometry/palette: trekhleb/bible-cross-references, MIT, commit 23bf0908858c949e519abe7a4ce7f4492f5fb3ba.
 * Cross-reference records retain OpenBible.info attribution and CC BY 4.0.
 */
const NS='http://www.w3.org/2000/svg';
let instance=0;
const el=(name,text,cls)=>{const n=document.createElement(name);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;};
const svgEl=(name,attrs={})=>{const n=document.createElementNS(NS,name);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));return n;};
const color=v=>/^#[0-9a-f]{6}$/i.test(v||'')?v:'#b8c4d1';
const finitePoints=points=>Array.isArray(points)&&points.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite));

export function renderVisual(container,payload,options={}){
  const defaults={'visual.title':'Engine A · Visual arcs','visual.links':'{count} bounded links','visual.noData':'No visual source geometry is available for this query.','visual.aria':'Bounded source cross-reference arcs for {reference}','visual.description':'Links are editorial source assertions. Colors indicate literary genre groups; brightness follows community votes, not theological certainty.','visual.edge':'{source} to {target}, {votes} source votes','visual.edgeTitle':'Votes: {votes} · Source line: {line}','visual.candidateWarning':'Corpus text alignment is verified separately from this source graph.','visual.source':'OpenBible.info cross-references · CC BY 4.0','visual.geometryCredit':'Arc geometry adapted from trekhleb/bible-cross-references (MIT).'};
  const tx=options.t||((key,params={})=>(defaults[key]||key).replace(/\{(\w+)\}/g,(_,name)=>params[name]??''));
  if(!container||typeof container.replaceChildren!=='function')throw new TypeError('A DOM container is required');
  const root=el('section',undefined,'visual-engine');
  const header=el('div',undefined,'visual-engine-header');
  header.append(el('strong',tx('visual.title')),el('span',payload?.reference||'', 'visual-engine-reference'));
  root.append(header);
  const status=payload?.status||'QUERY_ERROR';
  const results=Array.isArray(payload?.results)?payload.results:[];
  root.append(el('p',`${options.t?tx('status.'+status):status} · ${tx('visual.links',{count:results.length})}`, 'visual-engine-status'));
  const layout=payload?.layout;
  if(!layout||!Number.isFinite(layout.width)||!Number.isFinite(layout.height)){
    root.append(el('p',tx('visual.noData')));
    container.replaceChildren(root);return{root,svg:null,node_count:0,edge_count:0,cleanup:()=>root.remove()};
  }
  const uid=++instance;
  const svg=svgEl('svg',{viewBox:`0 0 ${layout.width} ${layout.height}`,role:'img','aria-label':tx('visual.aria',{reference:payload.reference})});
  svg.classList.add('visual-engine-canvas');
  const desc=svgEl('desc');desc.textContent=tx('visual.description');svg.append(desc);
  const defs=svgEl('defs');svg.append(defs);
  const vertical=layout.orientation==='vertical';
  const along=index=>layout.axis_start+(index-layout.view_start)/(layout.view_end-layout.view_start)*(layout.axis_end-layout.axis_start);
  const line=vertical?{x1:layout.baseline,y1:layout.axis_start,x2:layout.baseline,y2:layout.axis_end}:{x1:layout.axis_start,y1:layout.baseline,x2:layout.axis_end,y2:layout.baseline};
  svg.append(svgEl('line',{...line,stroke:'#718096','stroke-width':1}));
  const genres=Array.isArray(payload.genres)?payload.genres:[];
  for(const g of genres){
    const a=along(g.first_index);const b=along(g.last_index+1);
    const rect=vertical?{x:layout.baseline-8,y:a,width:5,height:Math.max(.5,b-a)}:{x:a,y:layout.baseline+5,width:Math.max(.5,b-a),height:5};
    svg.append(svgEl('rect',{...rect,fill:color(g.color)}));
  }
  const edges=Array.isArray(payload.edges)?payload.edges:[];
  edges.forEach((edge,index)=>{
    const points=edge?.geometry?.points;if(!finitePoints(points)||points.length<2)return;
    const gradientId=`visual-gradient-${uid}-${index}`;
    const grad=svgEl('linearGradient',{id:gradientId,gradientUnits:'userSpaceOnUse',x1:points[0][0],y1:points[0][1],x2:points.at(-1)[0],y2:points.at(-1)[1]});
    grad.append(svgEl('stop',{offset:'0%', 'stop-color':color(edge.source_color)}),svgEl('stop',{offset:'100%','stop-color':color(edge.target_color)}));defs.append(grad);
    const path=svgEl('path',{d:points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' '),fill:'none',stroke:`url(#${gradientId})`,'stroke-width':1.8,opacity:Math.max(.2,Math.min(1,edge.weight??.4)),tabindex:0,role:'button','aria-label':tx('visual.edge',{source:edge.source_reference,target:edge.target_reference,votes:edge.votes})});
    path.classList.add('visual-engine-arc');
    const title=svgEl('title');title.textContent=`${edge.source_reference} → ${edge.target_reference}\n${tx('visual.edgeTitle',{votes:edge.votes,line:edge.source_line_number})}`;path.append(title);
    const activate=()=>container.dispatchEvent(new CustomEvent('visual-reference-select',{bubbles:true,detail:{reference:edge.direction==='incoming'?edge.source_reference:edge.target_reference,source_reference:edge.source_reference,target_reference:edge.target_reference,direction:edge.direction}}));
    path.addEventListener('click',activate);path.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activate();}});
    svg.append(path);
  });
  const nodes=Array.isArray(payload.nodes)?payload.nodes:[];
  for(const node of nodes){
    if(!Number.isFinite(node.x)||!Number.isFinite(node.y))continue;
    const dot=svgEl('circle',{cx:node.x,cy:node.y,r:node.is_focus?4.6:2.2,fill:color(node.color),stroke:node.is_focus?'#fff':'none','stroke-width':1.2});
    const title=svgEl('title');title.textContent=node.reference;dot.append(title);svg.append(dot);
  }
  root.append(svg);
  const legend=el('ul',undefined,'visual-engine-legend');
  const genreKeys={'Law':'law','History':'history','Wisdom':'wisdom','Poetry & Wisdom':'wisdom','Major Prophets':'majorProphets','Minor Prophets':'minorProphets','Gospels':'gospels','Acts':'acts','Pauline Epistles':'paulineEpistles','General Epistles':'generalEpistles','Revelation':'revelation'};
  for(const g of genres){const item=el('li');const swatch=el('span',undefined,'visual-engine-swatch');swatch.style.backgroundColor=color(g.color);item.append(swatch,document.createTextNode(options.t&&genreKeys[g.name]?tx('genres.'+genreKeys[g.name]):String(g.name)));legend.append(item);}root.append(legend);
  root.append(el('p',`${options.t?tx('status.'+(payload.mapping?.status||'UNMAPPED_REFERENCE')):payload.mapping?.status||'UNMAPPED_REFERENCE'} · ${tx('visual.candidateWarning')}`, 'visual-engine-mapping'));
  const credit=el('p',undefined,'visual-engine-credit');
  const source=el('a',tx('visual.source'));source.href='https://www.openbible.info/labs/cross-references/';source.rel='noreferrer';
  credit.append(source,document.createTextNode(' · '+tx('visual.geometryCredit')));root.append(credit);
  container.replaceChildren(root);
  return{root,svg,node_count:nodes.length,edge_count:edges.length,cleanup:()=>root.remove()};
}
export default renderVisual;
