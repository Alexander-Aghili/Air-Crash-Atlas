function dateAliases(date){const parts=date.split("-");return parts.length===3?`${Number(parts[1])}/${Number(parts[2])} ${Number(parts[1])}-${Number(parts[2])}`:"";}
import { aircraftGroups } from './appearance.js?v=20261004-mixed-collisions';
export class CrashCatalog {
  constructor(data) {
    if(data.type!=='FeatureCollection'||!Array.isArray(data.features))throw Error('The archive dataset is invalid.');
    this.features=[...data.features].sort((a,b)=>b.properties.date.localeCompare(a.properties.date));
    this.searchIndex=new Map(this.features.map(f=>[f.id,[f.properties.name,f.properties.date,dateAliases(f.properties.date),(f.properties.search_aliases||[]).join(" "),f.properties.location_text,f.properties.state,f.properties.description,JSON.stringify(f.properties.aircraft),f.properties.source_locator].join(' ').toLowerCase()]));
  }
  filter({query='',state='',quality='',category='',categories=null,type='',from='',to='',aircraft='',media='',scope='all',decades=null,aircraftGroup=''}={}) {
    return this.features.filter(f=>{
      const p=f.properties,year=Number(p.date.slice(0,4));
      const site=!!f.geometry && ['impact site','event site'].includes(p.location_kind);
      return (decades===null || decades.includes(Math.floor(year/10)*10)) && (!aircraftGroup || aircraftGroups(p).includes(aircraftGroup)) && (scope!=='sites'||site) && (!query||this.searchIndex.get(f.id).includes(query.toLowerCase())) && (!state||p.state===state) && (!quality||p.location_quality===quality) && (!category||p.civil_or_military===category) && (categories===null||categories.includes(p.civil_or_military)) && (!type||p.event_type===type) && (!from||year>=Number(from)) && (!to||year<=Number(to)) && (!aircraft||[JSON.stringify(p.aircraft),p.description||''].join(' ').toLowerCase().includes(aircraft.toLowerCase())) && (!media || (media==='images' ? !!p.images?.length : (p.media||[]).some(m=>media==='any'||m.kind===media)));
    });
  }
}
