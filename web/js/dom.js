export const $ = id => document.getElementById(id);
export const num = n => n.toLocaleString();
export function safeURL(value) {
  try { const u=new URL(value); return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password ? u.href : null; } catch { return null; }
}
export function validSource(value) { const safe=safeURL(value);return !!safe && new URL(safe).hostname==='en.wikipedia.org'; }
export function link(text,url,className='') {
  const a=document.createElement('a');a.textContent=text;a.className=className;
  const safe=safeURL(url);if(safe){a.href=safe;a.target='_blank';a.rel='noopener noreferrer';a.setAttribute('aria-label',`${text} (opens a new tab)`);}return a;
}
export function imageURL(value) { const safe=safeURL(value);return safe && ['upload.wikimedia.org','thumb.wikimedia.org'].includes(new URL(safe).hostname) ? safe : null; }
export function node(tag,text='',className='') { const el=document.createElement(tag);el.textContent=text;el.className=className;return el; }
export function sourceLink(p) { return link(`${p.name} ↗`,p.source_url,'result-title'); }
export function sitePoints(f) { return f.geometry ? (f.properties.site_geometries?.length ? f.properties.site_geometries : [f.geometry]) : []; }
export const siteLabel=f=>!f.geometry?'No event-site coordinates':f.properties.location_kind==='event site'?'Event location from Wikipedia':f.properties.location_quality==='approximate'?'Approximate crash site':'Coordinates from Wikipedia';
