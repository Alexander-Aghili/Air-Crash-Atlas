# Plane Crash Locations Web Map Build Plan

Implementation guide | 2 October 2026

## Goal

Create an independent, worldwide web map of plane crash locations, including civil, military, historical, and obscure accidents. Clicking a crash marker opens a detail panel with its date, aircraft, location evidence, and links to Wikipedia, original reports, historical accounts, Mentour Pilot videos, and Air Crash Investigation episodes when available. Source and media links open in a new tab so visitors can return to the map.

Include events documented only in Wikipedia list entries. A dedicated article, Wikidata item, or documentary episode is not required. Map actual crash sites where evidence supports them, visibly distinguish approximate positions, and retain unlocated events in searchable results. Incidents and combat losses discovered alongside crashes should be identified and available through separate filters.

## Architecture and data model

Use a Python ingestion and review pipeline to produce versioned event JSON and GeoJSON. Serve these with a static responsive web app using Leaflet and marker clustering. Fetch and reconcile sources during dataset updates rather than scraping source sites in each visitor’s browser. Select a basemap provider appropriate for the expected traffic and retain its required attribution.

| Field | Purpose |
| --- | --- |
| event_id and title | Stable event identity and displayed name |
| date and date_precision | Exact date, partial date, range, or competing dates |
| event_type and civil_or_military | Crash, collision, disappearance, ground incident, or combat loss |
| aircraft | Array of aircraft types, registrations, military serials, operators, and units |
| location_text and geometry | Original geographic description and point or area in WGS84, or null |
| location_kind and quality | Impact site, approximate area, last-known position, or other explicitly labeled location; verification status |
| uncertainty and evidence | Justified radius or area when known, derivation method, and supporting sources |
| sources | URLs, Wikipedia sections or article IDs, source revisions, and retrieval dates |
| media | Verified video or episode links, titles, provider, edition, and match evidence |

Keep one event record for a collision involving multiple aircraft, with multiple aircraft and site geometries where appropriate. Memorials and later wreckage displays are separate related places, not substitute crash coordinates.

## Step by step implementation

### Step 1  Build a source inventory

Start with Wikipedia’s military aircraft accident index and its chronological lists, civil accident lists, dedicated accident articles, and the Mayday episode list. Follow list references for obscure events. Supplement US civil records through NTSB and historical or military records through report archives, local historical societies, specialist accounts, and contemporary newspapers. These sources have different coverage; the initial map is a sourced catalog rather than a claim to include every crash worldwide.

Use supported Wikimedia data access methods where available, cache retrieved pages and revisions, and fetch conservatively with bounded retries and backoff. Track every source page as pending, fetched, parsed, failed, or needing review.

### Step 2  Test representative cases

Build a pilot dataset containing a well-known civil crash with coordinates, a military crash with a dedicated article, an event described only in a list, an offshore disappearance, and a collision involving multiple aircraft. Include the White Hill B-17 event described in Step 7. Validate extraction, source links, location interpretation, and deduplication before expanding to the full inventory.

### Step 3  Discover military events through Wikipedia lists

Treat these as required discovery sources:

- [Military aircraft accidents and incidents index](https://en.wikipedia.org/wiki/List_of_accidents_and_incidents_involving_military_aircraft)
- [Military aircraft accidents and incidents from 1945 to 1949](https://en.wikipedia.org/wiki/List_of_accidents_and_incidents_involving_military_aircraft_(1945%E2%80%931949))

Follow every chronological list linked from the index, rather than limiting ingestion to 1945–1949. Discover aircraft-model and conflict lists as additional sources, deduplicate overlapping events, and record which source families have been processed. The chronological lists are not a complete catalog of military losses; the 1945–1949 page generally excludes combat losses except for selected cases. Preserve event type so accidents, ground incidents, disappearances, and combat losses can be filtered separately.

### Step 4  Extract list entries without requiring standalone articles

Parse year or period headings and each dated entry. Carry the year into the date, preserve uncertain or conflicting dates, and distinguish multiple events listed under the same day. A multi-aircraft collision remains one event with multiple aircraft records. Capture aircraft type, military serial or registration, operator and unit, location wording, linked places, citations, and any dedicated accident article.

Do not require a standalone Wikipedia article or a Wikidata event item. Many useful records exist only as paragraphs in these lists. Link such records to the verified containing section of the list page, and display the event date and aircraft serial so readers can find the paragraph. Do not invent a per-event anchor. Retain the page revision identifier and a short identifying excerpt or source locator for later reconciliation.

### Step 5  Resolve crash locations with explicit uncertainty

Prefer event-specific coordinates from a dedicated accident article, Wikidata event item, original report, or a corroborated historical account. A linked town or airport supplies geographic context, not automatically the impact location. Preserve phrases such as “near”, “offshore”, and distances with bearings. Derived positions need a recorded method and uncertainty; broad regions remain approximate areas or unlocated records.

Follow each entry’s citations to military report indexes, local histories, newspapers, and specialist archives when the Wikipedia entry lacks coordinates. For historical maps, align stable landmarks to a modern basemap, validate against additional landmarks, and transform the resulting location to WGS84. Record the map date, alignment method, and justified uncertainty. Keep impact sites, memorials, recovered wreckage locations, and departure or destination airports distinct.

### Step 6  Match events and media

Deduplicate using date, military serial or registration, aircraft type, and operator, with review for conflicts. Match civil records through Wikipedia lists, Wikidata, and official investigation records using the same approach. Maintain multiple source links for each event.

Search for Mentour Pilot coverage using event identifiers and verify the video description or content before attaching it. Match Air Crash Investigation or Mayday episodes to their documented subjects, recording episode title, series edition, season and episode when confirmed, and a verified information or viewing link. Missing media is valid; it must not prevent obscure events from appearing. One episode can cover multiple accidents and one accident can have multiple videos or episodes.

### Step 7  Validate with the Marin B17 example

Use the 16 May 1946 entry for B-17G-95-VE serial 44-85510 as a regression case. The 1945–1949 list describes a crash into White’s Hill near Fairfax while en route to Hamilton Field and links to the dedicated Fairfax B-17 article and historical sources. Merge the list entry and dedicated article into one event. Confirm the location through evidence before assigning a precise marker; do not substitute Hamilton Field’s coordinates or Mount Tamalpais’s summit.

### Step 8  Build the map interface

Display clustered markers with a searchable results list and filters for year or date range, country, aircraft, civil or military, event type, location quality, and available media. Clicking a cluster zooms or expands it. Clicking an individual event opens a detail panel with a short factual description, uncertainty label, and separate Wikipedia, report, historical-source, video, and episode links.

Give list-only events a working link to their containing Wikipedia section and show their date and aircraft serial. Give unlocated events a source-linked result without a fabricated marker. Make the map, result list, detail panel, and external links accessible by keyboard and on mobile. Show uncertainty through both text and marker styling. Validate external URLs, escape extracted labels, and use safe new-tab links.

### Step 9  Check extraction and map behavior

Reconcile discovered pages and entries against ingestion results. Report events extracted, merged, mapped, approximate, unlocated, and awaiting review. Validate longitude-first GeoJSON order, geographic bounds, date inheritance, multiple entries on the same day, aircraft serials, and multi-aircraft events. Review a sample from each source layout and flag discrepancies.

Check marker and source navigation, list-section anchors, media matches, filter combinations, search aliases, mobile and keyboard use, and dataset or basemap loading failures. Verify that airport, town, memorial, and last-known coordinates cannot silently appear as confirmed impact sites. Broken or absent media must not remove an event from the map.

### Step 10  Publish and maintain the crash map

Provide year, aircraft, civil or military, event-type, location-quality, and available-media filters. Display mapped and unlocated counts separately. Test list-only events, absent coordinates, multiple aircraft, duplicate listings, conflicting dates, and unmatched media. Retain source revisions and reviewed overrides during refreshes. Add source attribution for each dataset and preserve applicable reuse requirements when reproducing source text.

## Additional starting references

- [Civil airliner accidents by location](https://en.wikipedia.org/wiki/List_of_accidents_and_incidents_involving_airliners_by_location)
- [Mayday and Air Crash Investigation episode list](https://en.wikipedia.org/wiki/List_of_Mayday_episodes)
- [Fairfax California B-17 crash](https://en.wikipedia.org/wiki/Fairfax,_California_B-17_crash)
- [Check-Six account of B-17 44-85510](https://www.check-six.com/Crash_Sites/Marin_B-17_crash.htm)
- [NTSB aviation investigation search](https://my.ntsb.gov/aviation)
- [NTSB location field limitations](https://www.ntsb.gov/Pages/AviationQueryHelp.aspx/1000)
- [Example Wikidata event record for USAir Flight 427](https://www.wikidata.org/wiki/Q929721)
- [USGS historical map downloads](https://ngmdb.usgs.gov/topoview/help/)

The military index and 1945–1949 page linked in Step 3 are required sources. Wikipedia citations are leads to investigate; preserve disagreements instead of presenting an unresolved account as confirmed.
