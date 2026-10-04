import { AIRCRAFT_GROUPS } from './appearance.js';
import { ResultsView } from './results.js';
import { $, num, node, link, imageURL, sitePoints, siteLabel } from './dom.js';
import { CrashCatalog } from './catalog.js';
import { CrashMap } from './map.js';
import { PAGE_SIZE } from './constants.js';
const FILTERS=['search','state','quality','event-type','year-from','year-to','aircraft','media','aircraft-group'];
export class CrashApplication {
  constructor(){this.visible=[];this.limit=PAGE_SIZE;this.selected=null;this.scope='sites';this.updating=false;this.decades=null;this.mapView=new CrashMap(this);this.results=new ResultsView(this);}
  get features(){return this.catalog?.features||[];}
  message(text){$('map-error-text').textContent=text;$('map-error').hidden=false;}
  saveState(){
    if(this.updating)return;const p=new URLSearchParams();
    for(const id of FILTERS)if($(id).value)p.set(id==='search'?'q':id,$(id).value);
    if($('color-by').value!=='fatalities')p.set('color',$('color-by').value);
    const categories=[...($('commercial-enabled').checked?['civil']:[]),...($('military-enabled').checked?['military']:[])];
    if(categories.length!==2)p.set('categories',categories.join(','));
    if(this.decades!==null)p.set('decades',this.decades.join(','));
    if(this.scope==='all')p.set('scope','all');if($('in-view').checked)p.set('inview','1');if(this.selected)p.set('event',this.selected);
    if(this.mapView.activeLayer==='satellite')p.set('layer','satellite');
    if(this.mapView.map){const c=this.mapView.map.getCenter();p.set('lat',c.lat.toFixed(4));p.set('lon',c.lng.toFixed(4));p.set('z',this.mapView.map.getZoom());}
    history.replaceState(null,'',`${location.pathname}${p.size?'?'+p:''}`);
  }
  setScope(scope){this.scope=scope==='all'?'all':'sites';$('scope-sites').setAttribute('aria-pressed',String(this.scope==='sites'));$('scope-all').setAttribute('aria-pressed',String(this.scope==='all'));}
  resetResults(){this.limit=PAGE_SIZE;this.render();$('result-scroll').scrollTop=0;}
  render(updateMap=true){
    const matching=this.catalog.filter({query:$('search').value.trim(),state:$('state').value,quality:$('quality').value,categories:[...($('commercial-enabled').checked?['civil']:[]),...($('military-enabled').checked?['military']:[])],type:$('event-type').value,from:$('year-from').value,to:$('year-to').value,aircraft:$('aircraft').value,media:$('media').value,scope:this.scope,decades:this.decades,aircraftGroup:$('aircraft-group').value});
    const bounds=this.mapView.map?.getBounds();this.visible=matching.filter(f=>!$('in-view').checked||!bounds||sitePoints(f).some(g=>bounds.contains([g.coordinates[1],g.coordinates[0]])));
    if(updateMap&&this.mapView.clusters){this.mapView.clusters.clearLayers();this.mapView.clusters.addLayers(matching.filter(f=>f.geometry).flatMap(f=>this.mapView.markers.get(f.id)||[]));}
    this.results.render();const mapped=this.visible.filter(f=>f.geometry).length,unlocated=this.visible.length-mapped;
    $('status').textContent=this.scope==='sites'?`${num(mapped)} ${mapped===1?'crash':'crashes'} on the map`:`${num(this.visible.length)} records · ${num(unlocated)} without coordinates`;
    this.saveState();
  }
  restore(){
    this.updating=true;const p=new URLSearchParams(location.search);
    for(const id of FILTERS)$(id).value=p.get(id==='search'?'q':id)||'';
    const categories=p.has('categories')?p.get('categories').split(','):p.get('category')?[p.get('category')]:['civil','military'];
    $('commercial-enabled').checked=categories.includes('civil');$('military-enabled').checked=categories.includes('military');
    $('color-by').value=['fatalities','year','none'].includes(p.get('color'))?p.get('color'):'fatalities';
    this.decades=p.has('decades')?p.get('decades').split(',').filter(Boolean).map(Number).filter(d=>this.availableDecades.includes(d)):null;this.syncDecades();this.mapView.updateAppearance();
    this.setScope(p.get('scope')==='all'||p.get('quality')==='missing'?'all':'sites');$('in-view').checked=p.get('inview')==='1';
    const lat=Number(p.get('lat')),lon=Number(p.get('lon')),z=Number(p.get('z'));
    if(this.mapView.map&&p.has('lat')&&p.has('lon')&&p.has('z')&&Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=85&&Math.abs(lon)<=180&&z>=2&&z<=19)this.mapView.map.setView([lat,lon],z);
    this.mapView.setLayer(p.get('layer'));this.updating=false;
    $('advanced').open=['quality','event-type','aircraft','media','aircraft-group'].some(id=>$(id).value);
    this.render();const selected=this.features.find(f=>f.id===p.get('event'));if(selected)this.showDetail(selected);
  }
  async init(){
    this.bindPageControls();
    try{
      const response=await fetch('data/events.geojson');if(!response.ok)throw Error('The records could not load. Reload to try again.');
      const data=await response.json();this.catalog=new CrashCatalog(data);this.displayCatalog(data.metadata);
      try{this.mapView.setupMap();}catch(error){this.message(error.message);$('in-view').disabled=true;for(const id of ['street','satellite','fit','view'])$(id).disabled=true;}
      this.bindCatalogControls();this.restore();
    }catch(error){$('status').textContent=error.message;this.message(error.message);$('refresh').textContent='Archive unavailable';}
  }
  syncDecades(){
    for(const input of $('decade-options').querySelectorAll('input')) input.checked=this.decades===null||this.decades.includes(Number(input.value));
    const n=this.decades===null?this.availableDecades.length:this.decades.length;
    $('decade-summary').textContent=n===this.availableDecades.length?'All decades':n===0?'No decades':`${n} ${n===1?'decade':'decades'} enabled`;
  }
  setDecades(values){this.decades=values.length===this.availableDecades.length?null:values;this.syncDecades();this.resetResults();}
  displayCatalog(meta){
    this.availableDecades=[...new Set(this.features.map(f=>Math.floor(Number(f.properties.date.slice(0,4))/10)*10).filter(Number.isFinite))].sort((a,b)=>a-b);
    for(const decade of this.availableDecades){const label=node('label','','check'),input=document.createElement('input');input.type='checkbox';input.value=decade;input.checked=true;label.append(input,document.createTextNode(`${decade}s`));$('decade-options').append(label);}
    for(const [value,label] of Object.entries(AIRCRAFT_GROUPS)){const option=node('option',label);option.value=value;$('aircraft-group').append(option);}

    const countries=[...new Set(this.features.map(f=>f.properties.state))].sort();for(const country of countries){const option=node('option',country);option.value=country;$('state').append(option);}
    $('total-stat').textContent=num(this.features.length);$('mapped-stat').textContent=num(this.features.filter(f=>f.geometry).length);
    const date=new Date(meta.generated_at).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});$('refresh').textContent=`Updated ${date} · ${num(meta.unlocated)} records without coordinates`;
    $('coverage').textContent=`${num(meta.total)} records: ${num(meta.mapped)} mapped and ${num(meta.unlocated)} without crash-site coordinates.`;
  }
  showDetail(f){
    this.selected=f.id;this.saveState();this.results.render();const p=f.properties,box=$('detail-content');box.replaceChildren();
    const images=p.images||[],hero=images.find(img=>imageURL(img.thumbnail));
    if(hero){const a=link('',hero.url,'detail-photo-link'),img=document.createElement('img');img.className='detail-photo';img.src=imageURL(hero.thumbnail);img.alt=hero.caption;img.onerror=()=>{a.hidden=true;};a.setAttribute('aria-label',`${hero.caption} — image and credits`);a.append(img);box.append(a,node('span',`${hero.caption} · Open image for credits`,'photo-credit'));}
    const inner=node('div','','detail-inner');inner.append(node('span',`${p.date} / ${p.civil_or_military.toUpperCase()} / ${p.event_type.toUpperCase()}`,'eyebrow'),node('h2',p.name));
    if(p.description)inner.append(node('p',p.description,'detail-summary'));
    const actions=node('div','','detail-actions');actions.append(link('Read Wikipedia ↗',p.article_url||p.source_url));if(images.length)actions.append(link('View image & credits ↗',images[0].url));
    if(f.geometry){const locate=node('button','Show crash site ⤢');locate.onclick=()=>this.mapView.locate(f);actions.append(locate);}inner.append(actions);
    const evidence=node('section','','evidence-card');evidence.append(node('h3',siteLabel(f).toUpperCase()),node('strong',p.location_text));
    for(const g of sitePoints(f)){const [lon,lat]=g.coordinates;evidence.append(node('span',`${lat.toFixed(5)}°, ${lon.toFixed(5)}°`,'coordinates'));}
    if(p.evidence?.method)evidence.append(node('p',p.evidence.method.startsWith('Event-specific coordinates')?'Wikipedia provides these crash-site coordinates. They have not been independently verified.':p.evidence.method));if(p.uncertainty?.description)evidence.append(node('p',p.uncertainty.description));if(p.uncertainty?.radius_m)evidence.append(node('p',`Source uncertainty: ${p.uncertainty.radius_m} m`));inner.append(evidence);
    const facts=node('div','','detail-facts');
    for(const [label,value] of [['AIRCRAFT',(p.aircraft||[]).map(a=>[a.type,a.registration,a.operator].filter(Boolean).join(' · ')).join(' / ')],['COUNTRY / AREA',p.state],['DATE',p.date],['EVENT',p.event_type],['FATALITIES',p.fatalities??'Not recorded']]){const item=node('div');item.append(node('small',label),node('span',value||'Not recorded'));facts.append(item);}inner.append(facts);
    if(images.length>1){inner.append(node('h3','Images','section-title'));const grid=node('div','','image-grid');for(const image of images){const a=link('',image.url);if(imageURL(image.thumbnail)){const img=document.createElement('img');img.src=imageURL(image.thumbnail);img.alt=image.caption;img.loading='lazy';img.onerror=()=>{img.hidden=true;};a.append(img);}a.setAttribute('aria-label',`${image.caption} — image and credits`);a.append(node('span',image.caption+' ↗'));grid.append(a);}inner.append(grid);}
    if(images.length)inner.append(node('p','Images may show the aircraft, crash site, or aftermath. Open an image for credits and its license.','detail-summary'));
    inner.append(node('h3','Sources','section-title'));const sources=node('ul','','source-list');
    for(const source of [...(p.sources||[]),...(p.media||[])]){const li=node('li');li.append(link(`${source.title||source.url} ↗`,source.url),node('small',source.provider||source.kind||'Wikipedia'));sources.append(li);}inner.append(sources);
    if(p.source_locator)inner.append(node('p',`List entry: ${p.source_locator}`,'detail-summary'));box.append(inner);box.scrollTop=0;$('detail-dialog').scrollTop=0;
    if(!$('detail-dialog').open)$('detail-dialog').show();$('close-detail').focus();
  }
  closeDetail(){ $('detail-dialog').close();this.selected=null;this.saveState();this.results.render();$('search').focus(); }
  setMobileView(view){
    document.body.dataset.mobileView=view;
    for(const name of ['map','records','filters'])$('mobile-'+name).setAttribute('aria-pressed',String(name===view));
    $('result-scroll').hidden=false;
    requestAnimationFrame(()=>this.mapView.map?.invalidateSize({pan:false}));
  }
  bindPageControls(){
    for(const view of ['map','records','filters'])$('mobile-'+view).onclick=()=>this.setMobileView(view);
    $('about').onclick=()=>$('about-dialog').showModal();$('close-about').onclick=()=>$('about-dialog').close();$('close-detail').onclick=()=>this.closeDetail();$('dismiss-error').onclick=()=>{$('map-error').hidden=true;};
    $('toggle-results').onclick=()=>{const expanded=$('toggle-results').getAttribute('aria-expanded')==='true';$('toggle-results').setAttribute('aria-expanded',String(!expanded));$('toggle-results').textContent=expanded?'Show list':'Hide list';$('result-scroll').hidden=expanded;};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('detail-dialog').open)this.closeDetail();if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('about-dialog').open&&!$('detail-dialog').open){e.preventDefault();$('search').focus();}});
    matchMedia('(max-width:760px)').addEventListener('change',e=>{if(!e.matches){$('result-scroll').hidden=false;$('toggle-results').setAttribute('aria-expanded','true');$('toggle-results').textContent='Hide list';}this.mapView.map?.invalidateSize();});
  }
  bindCatalogControls(){
    let timer;
    for(const id of FILTERS)$(id).addEventListener(['search','aircraft','year-from','year-to'].includes(id)?'input':'change',()=>{if(id==='quality'&&$('quality').value==='missing')this.setScope('all');clearTimeout(timer);timer=setTimeout(()=>this.resetResults(),id==='search'?100:0);});
    for(const id of ['commercial-enabled','military-enabled'])$(id).onchange=()=>this.resetResults();
    $('color-by').onchange=()=>{this.mapView.updateAppearance();this.saveState();};
    $('decade-options').onchange=()=>this.setDecades([...$('decade-options').querySelectorAll('input:checked')].map(i=>Number(i.value)));
    $('decades-all').onclick=()=>this.setDecades(this.availableDecades);$('decades-none').onclick=()=>this.setDecades([]);
    document.addEventListener('click',e=>{if(!$('decade-picker').contains(e.target))$('decade-picker').open=false;});
    $('decade-picker').addEventListener('keydown',e=>{if(e.key==='Escape'){$('decade-picker').open=false;$('decade-summary').focus();}});
    $('in-view').onchange=()=>this.resetResults();$('more').onclick=()=>{this.limit+=PAGE_SIZE;this.results.render();};
    for(const scope of ['sites','all'])$('scope-'+scope).onclick=()=>{this.setScope(scope);if(scope==='sites'&&$('quality').value==='missing')$('quality').value='';this.resetResults();};
    $('reset').onclick=()=>{for(const id of FILTERS)$(id).value='';$('in-view').checked=false;$('commercial-enabled').checked=true;$('military-enabled').checked=true;this.decades=null;this.syncDecades();$('color-by').value='fatalities';this.mapView.updateAppearance();this.setScope('sites');this.resetResults();};
    $('street').onclick=()=>this.mapView.setLayer('map');$('satellite').onclick=()=>this.mapView.setLayer('satellite');$('fit').onclick=()=>this.mapView.fit();
    $('view').onchange=()=>{if($('view').value==='all'){this.mapView.fit();return;}const views={world:[[20,0],2],us:[[38,-98],4],europe:[[50,15],4],asia:[[25,100],3]};const [center,zoom]=views[$('view').value];this.mapView.map?.setView(center,zoom);};window.addEventListener('popstate',()=>this.restore());
  }
}
