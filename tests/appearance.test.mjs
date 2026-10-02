import {test} from 'node:test';
import assert from 'node:assert/strict';
import {aircraftAppearance, aircraftGroups, fatalityCount, markerColor, markerHTML} from '../web/js/appearance.js';
import {CrashCatalog} from '../web/js/catalog.js';
test('aircraft models use ICAO and tar1090 symbols with conservative unknown fallback',()=>{
  for(const [name,code,group] of [['Boeing 737-300','B733','jet'],['Boeing 737 MAX 8','B38M','jet'],['Boeing 747-400','B744','heavy'],['Boeing 767-223ER [ b ]','B762','heavy'],['Boeing 767-222 [ b ]','B762','heavy'],['Boeing 767-300ER','B763','heavy'],['Boeing 767-400ER','B764','heavy'],['Boeing 757-223 [ a ]','B752','jet'],['Cessna 172','C172','prop'],['Cessna 310','C310','twin'],['UH-1','UH1','rotor'],['F-16','F16','fighter'],['B-17G-95-VE','B17','transport']]){
    const result=aircraftAppearance({type:name});assert.equal(result.code,code,name);assert.equal(result.group,group,name);
  }
  assert.equal(aircraftAppearance({type:'Unidentified aircraft'}).group,'unknown');
  assert.equal(aircraftAppearance({type:'<script>alert(1)</script>'}).group,'unknown');
  assert.ok(!markerHTML({aircraft:[{type:'<script>alert(1)</script>'}]}).includes('<script>'));
});
test('fatality colors preserve zero, reject ambiguous or unrecorded totals',()=>{
  for(const [raw,expected] of [[null,null],['',null],['0',0],['132',132],['1,500',1500],['14 or 17',null],['50–70',null],['10 + 2',null],['239 [ 1 ]',239],[-1,null],[1.5,null],['132 (including 2 on ground)',132]])assert.equal(fatalityCount(raw),expected,String(raw));
  assert.notEqual(markerColor({fatalities:'0'}),markerColor({fatalities:null}));
  assert.notEqual(markerColor({fatalities:'5'}),markerColor({fatalities:'500'}));
  assert.equal(markerColor({fatalities:null,date:'1950-01-01'},'none'),markerColor({fatalities:'500',date:'2025-01-01'},'none'));
  assert.notEqual(markerColor({date:'1950-01-01'},'year'),markerColor({date:'2025-01-01'},'year'));
  assert.notEqual(markerColor({date:'1950-01-01'},'year'),markerColor({date:'1951-01-01'},'year'));
  assert.equal(markerColor({},'year'),'#747f88');
});
test('decades combine with custom years and aircraft filters, including multi-aircraft collisions',()=>{
  const record=(id,date,aircraft)=>({id,geometry:{type:'Point',coordinates:[0,0]},properties:{date,aircraft,name:id,event_type:'collision',location_kind:'impact site'}});
  const data={type:'FeatureCollection',features:[record('a','1956-06-30',[{type:'DC-7'},{type:'Boeing 747-400'}]),record('b','1946-01-01',[{type:'F-16'}]),record('c','2001-09-11',[{type:'Boeing 757-200'}])]};
  const c=new CrashCatalog(data);
  assert.equal(c.filter({decades:null}).length,3);assert.equal(c.filter({decades:[]}).length,0);
  assert.deepEqual(c.filter({decades:[1950,2000],from:'1957'}).map(f=>f.id),['c']);
  assert.deepEqual(c.filter({decades:[1950],aircraftGroup:'heavy'}).map(f=>f.id),['a']);
  assert.deepEqual(aircraftGroups(data.features[0].properties),['transport','heavy']);
  assert.ok(markerHTML(data.features[0].properties).includes('multiple'));
});

test('both September 11 Boeing 767 records are mapped and survive heavy-aircraft filtering',async()=>{
  const {readFile}=await import('node:fs/promises');
  const data=JSON.parse(await readFile(new URL('../web/data/events.geojson',import.meta.url),'utf8'));
  const catalog=new CrashCatalog(data);
  const flights=catalog.filter({query:'9/11',scope:'sites',aircraftGroup:'heavy'});
  assert.deepEqual(flights.map(f=>f.properties.name).sort(),['American Airlines Flight 11','United Airlines Flight 175']);
  for(const flight of flights){
    assert.ok(flight.geometry);assert.ok(aircraftAppearance(flight.properties.aircraft[0]).shape);
    assert.equal(aircraftAppearance(flight.properties.aircraft[0]).group,'heavy');
    assert.ok(markerHTML(flight.properties).includes('<path'));
  }
});
