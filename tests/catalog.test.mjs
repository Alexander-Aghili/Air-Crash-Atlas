import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CrashCatalog} from '../web/js/catalog.js';
import {validSource} from '../web/js/dom.js';
const data={type:'FeatureCollection',features:[{id:'a',geometry:null,properties:{name:'B-17',date:'1946-05-16',state:'US',location_quality:'missing',civil_or_military:'military',event_type:'crash',aircraft:[{type:'B-17',registration:'44-85510'}],media:[]}},{id:'b',geometry:{type:'Point',coordinates:[0,0]},properties:{name:'Collision',date:'1956-06-30',state:'US',location_quality:'approximate',civil_or_military:'civil',event_type:'collision',aircraft:[{type:'DC-7'}],media:[{kind:'episode'}]}}]};
test('combined filters and serial search retain unlocated events',()=>{const c=new CrashCatalog(data);assert.equal(c.filter({query:'44-85510',category:'military',from:'1940',to:'1950',quality:'missing'}).length,1);assert.equal(c.filter({type:'collision',aircraft:'DC-7',media:'any'}).length,1);assert.equal(c.filter({from:'2000'}).length,0)});
test('Wikipedia source links reject unsafe or unrelated URLs',()=>{assert.ok(validSource('https://en.wikipedia.org/wiki/Test#1946'));for(const s of ['javascript:alert(1)','https://evil.com','https://user@en.wikipedia.org/wiki/Test'])assert.equal(validSource(s),false)});
test('crash site scope excludes unresolved records',()=>{data.features[1].properties.location_kind='impact site';const c=new CrashCatalog(data);assert.equal(c.filter({scope:'sites'}).length,1);assert.equal(c.filter({scope:'all'}).length,2)});
test('September 11 aliases and dates find all four crash records',()=>{const records=['American Airlines Flight 11','American Airlines Flight 77','United Airlines Flight 175','United Airlines Flight 93'].map((name,i)=>({id:String(i),geometry:{type:'Point',coordinates:[-74,40]},properties:{name,date:'2001-09-11',search_aliases:['9/11','September 11 attacks'],location_kind:'impact site',event_type:'crash',aircraft:[]}}));const c=new CrashCatalog({type:'FeatureCollection',features:records});for(const query of ['9/11','September 11','2001-09-11'])assert.equal(c.filter({query,scope:'sites'}).length,4)});

test('aviation categories can be enabled independently or both disabled',()=>{const c=new CrashCatalog(data);assert.equal(c.filter({categories:['civil','military']}).length,2);assert.deepEqual(c.filter({categories:['military']}).map(f=>f.id),['a']);assert.deepEqual(c.filter({categories:['civil']}).map(f=>f.id),['b']);assert.equal(c.filter({categories:[]}).length,0)});

test('mapped scope includes source-located accidents and incidents consistently',()=>{
  const features=['crash','accident','incident'].map((type,i)=>({id:String(i),geometry:{type:'Point',coordinates:[0,0]},properties:{name:`Event ${i}`,date:'2023-10-22',event_type:type,location_kind:type==='crash'?'impact site':'event site',aircraft:[]}}));
  features.push({id:'unlocated',geometry:null,properties:{name:'Unlocated incident',date:'2023-10-22',event_type:'incident',location_kind:'unknown',aircraft:[]}});
  const catalog=new CrashCatalog({type:'FeatureCollection',features});
  assert.equal(catalog.filter({scope:'sites'}).length,3);
  assert.equal(catalog.filter({scope:'all'}).length,4);
  assert.equal(catalog.filter({scope:'sites',type:'incident'}).length,1);
});
