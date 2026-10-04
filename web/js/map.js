import { markerHTML, markerDescription, FATALITY_BINS, YEAR_STOPS } from './appearance.js?v=20261004-civil-location';
import { PAGE_SIZE } from "./constants.js?v=20261004-civil-location";
import { $, num, sitePoints } from "./dom.js?v=20261004-civil-location";
export class CrashMap {
  constructor(app) {
    this.app = app;
    this.map = null;
    this.clusters = null;
    this.markers = new Map();
    this.activeLayer = "map";
    this.layers = {};
  }
  icon(p) {
    return L.divIcon({html: markerHTML(p, $('color-by').value),className:'event-marker',iconSize:[48,48],iconAnchor:[24,24]});
  }
  updateAppearance() {
    const mode=$('color-by').value;
    for (const f of this.app.features) for (const marker of this.markers.get(f.id)||[]) marker.setIcon(this.icon(f.properties));
    this.renderLegend(mode);
  }
  renderLegend(mode=$('color-by').value) {
    $('color-key-title').textContent=mode==='year'?'Year':mode==='none'?'Markers':'Fatalities';
    const key=$('color-key');key.replaceChildren();
    if(mode==='year'){
      const ramp=document.createElement('div'),labels=document.createElement('div');ramp.className='year-color-ramp';labels.className='year-color-labels';
      ramp.style.background=`linear-gradient(to right, ${YEAR_STOPS.map(s=>`${s.color} ${(s.year-1900)/130*100}%`).join(',')})`;
      for(const label of ['≤1900','1960','≥2030']){const text=document.createElement('span');text.textContent=label;labels.append(text);}
      key.append(ramp,labels);
    }
    for(const bin of mode==='year'?[]:mode==='none'?[{label:'All crashes',color:'#233f50'}]:FATALITY_BINS){
      const item=document.createElement('span'), swatch=document.createElement('i');
      swatch.style.backgroundColor=bin.color;item.append(swatch,document.createTextNode(bin.label));key.append(item);
    }

  }
  locate(f) {
    if (!this.map) return;
    if(matchMedia('(max-width:760px)').matches){
      this.app.setMobileView('map');
      if($('detail-dialog').open)this.app.closeDetail();
      this.map.invalidateSize({pan:false});
    }
    this.app.selected = f.id;
    const m = this.markers.get(f.id)?.[0];
    if (!m) return;
    this.clusters.zoomToShowLayer(m, () => {
      this.map.setView(m.getLatLng(), Math.max(this.map.getZoom(), 14), {
        animate: !matchMedia("(prefers-reduced-motion: reduce)").matches,
      });
      m.openTooltip();
    });
    this.app.results.render();
  }
  setLayer(name) {
    this.activeLayer = name === "satellite" ? "satellite" : "map";
    if (this.map) {
      for (const layer of Object.values(this.layers))
        if (this.map.hasLayer(layer)) this.map.removeLayer(layer);
      this.layers[this.activeLayer].addTo(this.map);
      $("map-error").hidden = true;
    }
    $("street").setAttribute(
      "aria-pressed",
      String(this.activeLayer === "map"),
    );
    $("satellite").setAttribute(
      "aria-pressed",
      String(this.activeLayer === "satellite"),
    );
    this.app.saveState();
  }
  fit() {
    if (!this.map) return;
    const points = this.app.visible
      .filter((f) => f.geometry)
      .flatMap((f) => sitePoints(f).map(g=>[g.coordinates[1],g.coordinates[0]]));
    if (points.length)
      this.map.fitBounds(points, { padding: [65, 65], maxZoom: 14 });
    else this.app.message("No mapped locations match the current filters.");
  }
  setupMap() {
    if (!window.L || !L.markerClusterGroup)
      throw new Error(
        "The map could not load. You can still search the catalog and open source entries.",
      );
    this.map = L.map("map", {
      maxZoom: 19,
      minZoom: 2,
      zoomControl: false,
      worldCopyJump: true,
    }).setView([20, 0], 2);
    L.control.zoom({position: "bottomright"}).addTo(this.map);
    this.clusters = L.markerClusterGroup({
      showCoverageOnHover: false,
      removeOutsideVisibleBounds: true,
      maxClusterRadius: 48,
      iconCreateFunction: (cluster) =>
        L.divIcon({
          html: `<span class="cluster-disc ${cluster.getChildCount() >= 100 ? "large" : ""}">${num(cluster.getChildCount())}</span>`,
          className: "event-cluster",
          iconSize: [48, 48],
        }),
    });
    this.map.addLayer(this.clusters);
    this.layers.map = L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      },
    );
    this.layers.satellite = L.tileLayer(
      "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          'Imagery &copy; <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri</a>, Vantor, Earthstar Geographics & GIS User Community',
      },
    );
    for (const [name, layer] of Object.entries(this.layers))
      layer.on("tileerror", () => {
        if (this.activeLayer === name)
          this.app.message(
            `${name === "satellite" ? "Satellite imagery" : "Map tiles"} are unavailable. Try the other basemap; catalog links remain available.`,
          );
      });
    for (const f of this.app.features) {
      if (!f.geometry) continue;
      const p = f.properties;
      const eventMarkers = [];
      for (const geometry of sitePoints(f)) {
      const [lon, lat] = geometry.coordinates;
      const m = L.marker([lat, lon], {
        title: `${p.name} (event details)`,
        alt: p.name,
        keyboard: true,
        icon: this.icon(p),
      });
      const label = document.createElement("div"),
        title = document.createElement("span"),
        quality = document.createElement("small");
      title.textContent = p.name;
      quality.textContent = `${markerDescription(p)} · ${p.location_quality}`;
      label.append(title, quality);
      m.bindTooltip(label, { direction: "top", offset: [0, -10] });
      m.on("click", () => this.app.showDetail(f));
      eventMarkers.push(m);
      }
      this.markers.set(f.id, eventMarkers);
    }
    this.renderLegend();
    this.map.on("moveend", () => {
      const c = this.map.getCenter();
      $("map-location").textContent =
        `${Math.abs(c.lat).toFixed(2)}° ${c.lat >= 0 ? "N" : "S"}   ${Math.abs(c.lng).toFixed(2)}° ${c.lng >= 0 ? "E" : "W"}`;
      if ($("in-view").checked) {
        this.app.limit = PAGE_SIZE;
        this.app.render(false);
      } else this.app.saveState();
    });
  }
}
