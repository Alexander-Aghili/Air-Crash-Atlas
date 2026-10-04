import symbols from '../vendor/aircraft-symbols.js?v=20261004-civil-location';

// Match named models to ICAO designators, then use tar1090's own icon mapping.
// Family matches are visual approximations, not historical ADS-B broadcasts.
const MODELS = [
  [/\bboeing\s*737\s*(?:MAX\s*([789])|[-–]\s*([789])\s*MAX)\b/i, m => `B3${m[1]||m[2]}M`],
  [/\bboeing\s*737(?:\s*[-–]\s*([1-9])\d\d)?\b/i, m => `B73${m[1] || '7'}`],
  [/\bboeing\s*747(?:\s*[-–]\s*([1-8])\d\d)?\b/i, m => `B74${m[1] || '4'}`],
  [/\bboeing\s*757(?:\s*[-–]\s*([23])\d\d)?\b/i, m => `B75${m[1] || '2'}`],
  [/\bboeing\s*767(?:\s*[-–]\s*([234])\d\d)?\b/i, m => `B76${m[1] || '3'}`],
  [/\bboeing\s*777(?:\s*[-–]\s*([23])\d\d)?\b/i, m => `B77${m[1] || '2'}`],
  [/\bboeing\s*787(?:\s*[-–]\s*([89]))?\b/i, m => `B78${m[1] || '8'}`],
  [/\bboeing\s*707\b/i, 'B703'], [/\bboeing\s*727\b/i, 'B722'], [/\bboeing\s*720\b/i, 'B720'],
  [/\bairbus\s*A\s*(318|319|320|321|300|310|330|340|350|380)\b/i, m => ({300:'A306',310:'A310',330:'A333',340:'A343',350:'A359',380:'A388'}[m[1]] || `A${m[1]}`)],
  [/\b(?:douglas\s*)?DC\s*[-–]?\s*3\b|\b(?:C|R4D)\s*[-–]?\s*47\b/i, 'DC3'],
  [/\b(?:douglas\s*)?DC\s*[-–]?\s*4\b|\bC\s*[-–]?\s*54\b/i, 'DC4'],
  [/\b(?:douglas\s*)?DC\s*[-–]?\s*6\b/i, 'DC6'], [/\b(?:douglas\s*)?DC\s*[-–]?\s*7\b/i, 'DC7'],
  [/\b(?:douglas\s*)?DC\s*[-–]?\s*8\b/i, 'DC87'], [/\b(?:douglas\s*)?DC\s*[-–]?\s*9\b/i, 'DC93'],
  [/\b(?:douglas\s*)?DC\s*[-–]?\s*10\b/i, 'DC10'], [/\bMD\s*[-–]?\s*11\b/i, 'MD11'],
  [/\bMD\s*[-–]?\s*(80|81|82|83|87|88|90)\b/i, m => `MD${m[1]}`],
  [/\b(?:lockheed\s*)?L\s*[-–]?\s*1011\b|\btristar\b/i, 'L101'],
  [/\b(?:lockheed\s*)?L\s*[-–]?\s*(?:749|1049|1649)\b|\b(?:super\s*)?constellation\b/i, 'CONI'],
  [/\b(?:lockheed\s*)?L\s*[-–]?\s*188\b/i, 'L188'],
  [/\b(?:antonov\s*)?An\s*[-–]?\s*(2|12|22|24|26|28|32|72|124|225)\b/i, m => `AN${m[1]}`],
  [/\b(?:ilyushin\s*)?Il\s*[-–]?\s*(14|18|62|76|86|96)\b/i, m => `IL${m[1]}`],
  [/\b(?:tupolev\s*)?Tu\s*[-–]?\s*(104|124|134|154|204)\b/i, m => `T${m[1]}`],
  [/\b(?:yakovlev\s*)?Yak\s*[-–]?\s*(40|42)\b/i, m => `YK${m[1]}`],
  [/\bATR\s*[-–]?\s*(42|72)\b/i, m => `AT${m[1]}`], [/\b(?:fokker\s+(?:F\s*[-–]?\s*)?|F\s*[-–]?\s*)(27|28|50|70|100)\b/i, m => `F${m[1]}`],
  [/\bDHC\s*[-–]?\s*8\b|\bdash\s*8\b/i, 'DH8C'], [/\bDHC\s*[-–]?\s*6\b|\btwin otter\b/i, 'DHC6'],
  [/\bDHC\s*[-–]?\s*3\b/i, 'DHC3'], [/\bDHC\s*[-–]?\s*2\b|\bde havilland\s*beaver\b/i, 'DHC2'],
  [/\b(?:embraer\s*)?EMB\s*[-–]?\s*110\b/i, 'E110'], [/\b(?:embraer\s*)?(?:EMB|ERJ)\s*[-–]?\s*120\b/i, 'E120'],
  [/\b(?:embraer\s*)?(?:ERJ\s*[-–]?\s*)?145\b/i, 'E145'],
  [/\b(?:bombardier\s*)?CRJ\s*[-–]?\s*(200|700|900)\b/i, m => ({200:'CRJ2',700:'CRJ7',900:'CRJ9'}[m[1]])],
  [/\bsaab\s*340\b/i, 'SF34'], [/\b(?:hawker siddeley\s*)?HS\s*[-–]?\s*748\b/i, 'HS74'],
  [/\bcessna\s*(150|152|172|180|182|185|206|208|210|310|340|402|421)\b/i, m => ({208:'C208'}[m[1]] || `C${m[1]}`)],
  [/\b(?:piper\s*)?PA\s*[-–]?\s*(28|32|34|44)\b/i, m => ({28:'P28A',32:'PA32',34:'PA34',44:'PA44'}[m[1]])],
  [/\b(?:beechcraft\s*)?king air\b/i, 'BE20'], [/\b(?:beechcraft\s*)?1900\b/i, 'B190'],
  [/\b(?:pilatus\s*)?PC\s*[-–]?\s*12\b/i, 'PC12'],
  [/\b(?:let\s*)?L\s*[-–]?\s*410\b/i, 'L410'],
  [/\bvickers\s*viscount\b/i, 'VISC'],
  [/\bconvair\s*(?:CV\s*[-–]?\s*)?(240|340|440|580|880|990)\b/i, m => `CV${m[1]}`],
  [/\b(?:british aerospace\s*)?jetstream\s*(31|32|41)\b/i, m => `JS${m[1]}`],
  [/\bcaravelle\b/i, 'S210'],
  [/\b(?:boeing\s*)?B\s*[-–]?\s*(17|29|52)(?:[A-Z])?\b/i, m => `B${m[1]}`],
  [/\b(?:lockheed\s*)?C\s*[-–]?\s*130\b/i, 'C130'], [/\bC\s*[-–]?\s*141\b/i, 'C141'], [/\bC\s*[-–]?\s*17\b/i, 'C17'], [/\bC\s*[-–]?\s*5\b/i, 'C5'],
  [/\b(?:F|RF)\s*[-–]?\s*(4|5|14|15|16|18|22|35|104)\b/i, m => `F${m[1]}`],
  [/\bMiG\s*[-–]?\s*(15|17|19|21|23|25|29|31)\b/i, m => `MG${m[1]}`],
  [/\b(?:sukhoi\s*)?Su\s*[-–]?\s*(24|25|27|30|34|35)\b/i, m => `SU${m[1]}`],
  [/\b(?:mil\s*)?Mi\s*[-–]?\s*(2|8|17|24|26)\b/i, m => `MI${m[1]}`],
  [/\b(?:sikorsky\s*)?S\s*[-–]?\s*(61|76|92)\b/i, m => `S${m[1]}`],
  [/\b(?:agustawestland\s*)?AW\s*[-–]?\s*(109|119|139|169|189)\b/i, m => `A${m[1]}`],
  [/\b(?:bell\s*)(206|212|407|412)\b/i, m => `B${m[1]}`],
  [/\b(?:bell\s*)?UH\s*[-–]?\s*1\b|\bbell\s*204\b/i, 'UH1'],
  [/\b(?:sikorsky\s*)?(?:UH|S)\s*[-–]?\s*60\b/i, 'H60'], [/\b(?:boeing\s*)?CH\s*[-–]?\s*47\b/i, 'H47'],
];
export const AIRCRAFT_GROUPS = {
  prop: 'Single-engine prop', twin: 'Twin-engine prop', transport: 'Turboprop / transport',
  jet: 'Jet / airliner', heavy: 'Heavy jet', fighter: 'High-performance jet',
  rotor: 'Rotorcraft', glider: 'Glider', unknown: 'Unknown type',
};
const GROUP_SHAPES = {
  prop: ['cessna','single_turbo','pa24'], twin: ['twin_small','twin_large'],
  transport: ['c130','lancaster','b25','dc3'], fighter: ['hi_perf','md_f15','f5_tiger','tornado','hunter','l159','sb39','miragef1','f14','f15','f18','f35','typhoon','mirage','rafale'],
  rotor: ['helicopter','chinook','gyrocopter'], glider: ['glider'],
  heavy: ['heavy_2e','heavy_4e','b707','b52','md11','a380','a340','a350','b747','b777','b787','il_62'],
};
// Conservative fallback descriptions for ICAO types absent from tar1090's
// special-icon table. Uses its standard type-description icons.
const TYPE_DESCRIPTIONS = {
  C150:'L1P',C152:'L1P',C172:'L1P',C180:'L1P',C182:'L1P',C185:'L1P',C206:'L1P',C208:'L1T',C210:'L1P',
  C310:'L2P',C340:'L2P',C402:'L2P',C421:'L2P',P28A:'L1P',PA32:'L1P',PA34:'L2P',PA44:'L2P',
  DC3:'L2P',DC4:'L4P',DC6:'L4P',DC7:'L4P',AN2:'L1P',AN12:'L4T',AN22:'L4T',AN24:'L2T',AN26:'L2T',AN28:'L2T',AN32:'L2T',
  DHC2:'L1P',DHC3:'L1P',DHC6:'L2T',DH8C:'L2T',AT42:'L2T',AT72:'L2T',SF34:'L2T',HS74:'L2T',
  E110:'L2T',E120:'L2T',F27:'L2T',F50:'L2T',CONI:'L4P',L188:'L4T',IL14:'L2P',IL18:'L4T',
  B762:'L2J-H',B763:'L2J-H',B764:'L2J-H',
  A310:'L2J-M',A306:'L2J-H',DC87:'L4J-H',T104:'L2J-M',T124:'L2J-M',T134:'L2J-M',T204:'L2J-M',YK42:'L3J-M',IL76:'L4J-H',IL86:'L4J-H',IL96:'L4J-H',
  L410:'L2T',VISC:'L4T',CV240:'L2P',CV340:'L2P',CV440:'L2P',CV580:'L2T',CV880:'L4J-M',CV990:'L4J-M',JS31:'L2T',JS32:'L2T',JS41:'L2T',S210:'L2J-M',
  MI2:'H2T',MI8:'H2T',MI17:'H2T',MI24:'H2T',MI26:'H2T',S61:'H2T',S76:'H2T',S92:'H2T',A109:'H2T',A119:'H1T',A139:'H2T',A169:'H2T',A189:'H2T',B206:'H1T',B212:'H2T',B407:'H1T',B412:'H2T',
  UH1:'H1T',H60:'H2T',H47:'H2T',
};
export function aircraftAppearance(aircraft = {}) {
  const name=String(aircraft.type || '').trim().replace(/(\d)[A-Za-z]{1,3}(?=[\s-]|$)/g,'$1');
  const normalized=name.toUpperCase().replace(/[^A-Z0-9]/g,'');
  let code = (symbols.types[normalized] || TYPE_DESCRIPTIONS[normalized]) ? normalized : null;
  if (!code) for (const [pattern,value] of MODELS) {
    const m=name.match(pattern); if(m){code=typeof value==='function'?value(m):value;break;}
  }
  const description=TYPE_DESCRIPTIONS[code];
  const match=code && (symbols.types[code] || symbols.descriptions[description] || symbols.descriptions[description?.[0]] || (description==='L4P'?['lancaster',1]:description==='L3J-M'?['jet_swept',1]:null));
  if(!match) return {code:null,shape:null,group:'unknown',scale:1,label:'Unknown type'};
  const [shape,scale]=match;
  let group=Object.keys(GROUP_SHAPES).find(g=>GROUP_SHAPES[g].includes(shape)) || 'jet';
  // Some transports share a silhouette with jets. Use only recognized designators.
  if(/^(AN(2|12|22|24|26|28|32)|IL(14|18)|L188|CONI|DC[3467]|DHC[236]|DH8|AT|F(27|50)|SF34|HS74|E1(10|20)|B190|C130)/.test(code)) group='transport';
  if(/^(H60|H47|UH1)/.test(code)) group='rotor';
  if(description?.startsWith('H'))group='rotor';
  if(/^L[234]T$/.test(description)||description==='L4P')group='transport';
  if(description?.endsWith('-H'))group='heavy';
  // The 757 uses tar1090's twin-jet silhouette but is a large/high-vortex
  // aircraft, below the heavy category.
  if(['B752','B753'].includes(code))group='jet';
  if(description==='L1P')group='prop';
  if(description==='L2P' && !['DC3','DC4','DC6','DC7'].includes(code))group='twin';
  return {code,shape,group,scale,label:AIRCRAFT_GROUPS[group]};
}
export function aircraftGroups(properties) {
  const aircraft=properties.aircraft?.length?properties.aircraft:[{}];
  return [...new Set(aircraft.map(a=>aircraftAppearance(a).group))];
}

// Ambiguous totals (ranges, competing estimates, expressions) stay unknown.
export function fatalityCount(value) {
  if(typeof value==='number') return Number.isSafeInteger(value)&&value>=0?value:null;
  if(typeof value!=='string')return null;
  const text=value.replace(/\[\s*\d+\s*\]/g,'').trim();
  const m=text.match(/^(\d{1,3}(?:,\d{3})+|\d+)(?:\s*\((?:including|all|on board|aboard)\b[^)]*\))?\s*$/i);
  return m?Number(m[1].replaceAll(',','')):null;
}
export const FATALITY_BINS = [
  {label:'0',color:'#287d8e',min:0,max:0},
  {label:'1–9',color:'#e1ad39',min:1,max:9},
  {label:'10–49',color:'#d77a28',min:10,max:49},
  {label:'50–99',color:'#c64930',min:50,max:99},
  {label:'100–299',color:'#a1263b',min:100,max:299},
  {label:'300+',color:'#64203b',min:300,max:Infinity},
  {label:'Unknown',color:'#747f88',min:null,max:null},
];
export const YEAR_STOPS = [
  {year:1900,color:'#433c85'}, {year:1940,color:'#356998'},
  {year:1960,color:'#25858c'}, {year:1980,color:'#548138'},
  {year:2000,color:'#ae7a21'}, {year:2030,color:'#b74335'},
];
export function yearColor(year){
  if(!Number.isFinite(year))return '#747f88';
  if(year<=YEAR_STOPS[0].year)return YEAR_STOPS[0].color;
  if(year>=YEAR_STOPS.at(-1).year)return YEAR_STOPS.at(-1).color;
  const upper=YEAR_STOPS.findIndex(s=>s.year>=year),a=YEAR_STOPS[upper-1],b=YEAR_STOPS[upper],t=(year-a.year)/(b.year-a.year);
  return '#'+[1,3,5].map(i=>Math.round(parseInt(a.color.slice(i,i+2),16)*(1-t)+parseInt(b.color.slice(i,i+2),16)*t).toString(16).padStart(2,'0')).join('');
}
export function markerColor(p, mode='fatalities') {
  if(mode==='none')return '#233f50';
  if(mode==='year')return yearColor(p.date?Number(p.date.slice(0,4)):NaN);
  const value=fatalityCount(p.fatalities);
  const bins=FATALITY_BINS;
  return bins.find(b=>value!==null&&Number.isFinite(value)&&b.min!==null&&value>=b.min&&value<=b.max)?.color || '#747f88';
}
function shapeSVG(a, color) {
  if(!a.shape) return `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="6" fill="${color}" stroke="#fffdf9" stroke-width="2"/></svg>`;
  const s=symbols.shapes[a.shape];
  if(!s)return shapeSVG({shape:null},color);
  const attrs=`fill="${color}" stroke="#fffdf9" stroke-width="${s.strokeScale || 1}" stroke-linejoin="round" paint-order="stroke fill"`;
  const paths=(Array.isArray(s.path)?s.path:[s.path]).filter(Boolean).map(path=>`<path d="${path}" ${attrs}/>`).join('');
  const accents=(Array.isArray(s.accent)?s.accent:[s.accent]).filter(Boolean).map(path=>`<path d="${path}" fill="none" stroke="#fffdf9" stroke-width="${.6*(s.strokeScale||1)}"/>`).join('');
  return `<svg viewBox="${s.viewBox || `0 0 ${s.w} ${s.h}`}" aria-hidden="true"><g${s.transform?` transform="${s.transform}"`:''}>${paths}${accents}</g></svg>`;
}
export function markerHTML(p, mode='fatalities') {
  const appearances=(p.aircraft?.length?p.aircraft:[{}]).map(aircraftAppearance);
  const unique=[...new Map(appearances.map(a=>[a.shape||'unknown',a])).values()].slice(0,2);
  const color=markerColor(p,mode);
  const sizes={prop:23,twin:27,transport:31,jet:32,heavy:39,fighter:29,rotor:29,glider:27,unknown:23};
  return `<span class="aircraft-symbol ${p.location_quality==='approximate'?'approximate':''} ${unique.length>1?'multiple':''}">${unique.map(a=>`<span style="width:${Math.round(sizes[a.group]*Math.min(1.12,Math.max(.85,a.scale)))}px">${shapeSVG(a,color)}</span>`).join('')}</span>`;
}
export function markerDescription(p) {
  const models=(p.aircraft||[]).map(a=>a.type||'Unknown aircraft');
  const count=fatalityCount(p.fatalities);
  return `${p.date} · ${count===null?'Fatalities unknown':`${count} fatalities`} · ${models.join(' / ')||'Aircraft type unknown'}`;
}
