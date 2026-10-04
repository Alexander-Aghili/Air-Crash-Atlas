import { $, num, link, node, imageURL, siteLabel } from './dom.js?v=20261004-mixed-collisions';
import { PAGE_SIZE } from './constants.js?v=20261004-mixed-collisions';
export class ResultsView {
  constructor(app){this.app=app;}
  render(){
    const fragment=document.createDocumentFragment();
    if(!this.app.visible.length){const li=node('li',this.app.scope==='sites'?'No mapped events match. Try All records to include records without coordinates.':'No records match. Try another flight, place, or aircraft.','empty-results');fragment.append(li);}
    for(const f of this.app.visible.slice(0,this.app.limit)){
      const p=f.properties,li=node('li');li.classList.toggle('selected',this.app.selected===f.id);
      const top=node('div','','record-top'),date=node('time',p.date);date.dateTime=p.date;top.append(date,node('span',p.state==='Unknown'?'COUNTRY NOT RECORDED':p.state.toUpperCase()));li.append(top);
      const body=node('div','','record-body');const image=p.images?.find(img=>imageURL(img.thumbnail));
      if(image){const img=document.createElement('img');img.className='record-image';img.src=imageURL(image.thumbnail);img.alt=image.caption;img.loading='lazy';img.onerror=()=>{img.replaceWith(node('div',p.date.slice(0,4),'record-year'));};body.append(img);}else body.append(node('div',p.date.slice(0,4),'record-year'));
      const info=node('div','','record-info'),title=node('button',p.name,'record-title');title.setAttribute('aria-label',`Open record: ${p.name}`);title.onclick=()=>{if(f.geometry)this.app.mapView.locate(f);this.app.showDetail(f);};info.append(title,node('div',p.location_text,'result-meta'));body.append(info);li.append(body);
      const footer=node('div','','record-footer');footer.append(link('Wikipedia ↗',p.article_url||p.source_url));if(p.images?.length)footer.append(link('Image ↗',p.images[0].url));
      if(f.geometry&&this.app.mapView.map){const locate=node('button','Locate ⤢','locate-button');locate.setAttribute('aria-label',`Locate ${p.name}`);locate.onclick=()=>this.app.mapView.locate(f);footer.append(locate);}
      const note=node('div','','result-note'),dot=node('i','','quality-dot'+(p.location_quality==='approximate'?' approximate':!f.geometry?' missing':''));dot.setAttribute('aria-hidden','true');note.append(dot,node('span',siteLabel(f)));li.append(footer,note);fragment.append(li);
    }
    $('results').replaceChildren(fragment);$('more').hidden=this.app.visible.length<=this.app.limit;$('more').textContent=`Load ${num(Math.min(PAGE_SIZE,Math.max(0,this.app.visible.length-this.app.limit)))} more records`;
  }
}
