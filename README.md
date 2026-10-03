# Aviation Crash Atlas

A static Leaflet map of plane crashes with search, filters, Wikipedia links, and images. Mapped crashes shows records with crash-site coordinates. All records includes records without coordinates and incidents. Search accepts dates and terms such as `9/11` or `September 11`.

## Run

```sh
python3 -m http.server 8000 --directory web
```

Open http://localhost:8000. No build or backend is needed. Leaflet and basemaps require internet. Search and article links remain usable if map dependencies fail.

## Refresh

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pipeline.extract
```

The extractor runs discovery, article enrichment, duplicate merging, and publication in one command. It parses dated definition lists, bullets, and tables, including military model and conflict lists. Enrichment processes every discovered dedicated article rather than stopping at a country-ordered page budget. Redirect aliases resolve to their actual articles and are merged into the same event. Enrichment uses four workers with a global limit of one request per second, bounded retries, maxlag, and response caches. The default update checks current Wikipedia revision IDs and fetches changed pages. Use `--refresh` to force all pages to be downloaded, `--offline` to rebuild entirely from cache, and `--max-pages N` only for a bounded discovery trial. Normal updates require no manual JSON edits. Set `WIKIMEDIA_USER_AGENT` for the discovery client. Both stages use the same cached Wikimedia client and `WIKIMEDIA_USER_AGENT`.

Published files are `web/data/events.geojson`, `events.json`, and `coverage.json`; the previous GeoJSON is retained. Enrichment writes temporary files before replacement. Coverage includes page failures, unresolved layouts, country counts, and image coverage. Cached requests make interrupted enrichment restartable.

## Location evidence and coverage

Coordinates are extracted only from an event infobox's Site field, never from arbitrary article coordinates, origin or destination airports, nearby towns, or memorials. Disappearances and last-known or presumed locations remain unresolved. Multiple Site coordinates remain attached to one collision record and appear as multiple map markers. Source-supplied coordinates are labeled as article impact coordinates; they have not all been independently surveyed. Approximate reviewed sites receive dashed outlines and an uncertainty explanation.

The Fairfax B-17 crash (44-85510, 16 May 1946) uses an approximate point digitized from the annotated historical crash-site map. Its record links the image, Wikidata coordinate, and original derivation. The map datum conversion is undocumented, so the point is explicitly approximate. MH370 retains no impact point. Reviewed records in `pipeline/reviewed.json` preserve deliberate location overrides across refreshes.

The archive is still incomplete: list-only events require further location evidence, unsupported list layouts need review, and automatic event and country classification remains provisional. Completing the discovered article pass does not imply complete worldwide coverage. No coordinates are invented to increase marker counts.

## Images and sources

Images come from accident articles and Wikipedia PageImages metadata. They may depict the aircraft, aftermath, or site maps, as indicated by captions. Cards link directly to Wikipedia and available image file pages; detail panels show images and provenance. Wikimedia file pages provide authors and individual licenses. Wikipedia text is reused under CC BY-SA 4.0; revision IDs and retrieval dates are retained.

Mayday matches require an episode row linking the event article. Media links are informational, not promises of streaming availability. Independently verified historical sources, reports, and videos can be added to reviewed records.

## Checks

```sh
python3 -m unittest discover -s tests
python3 -m pipeline.validate
node --test tests/*.test.mjs
```

### Map appearance

Keep custom From/To years and independently enable decades in the decade dropdown.
Filters apply together to the map and record list; `decades=` in a saved URL means
all decades disabled, while an absent parameter enables all. `color=fatalities`,
`color=year`, or `color=none` controls marker colors independently of date filters.
Fatalities is the default; missing and ambiguous totals remain gray (zero is distinct).
Clusters remain neutral site counts, not fatality totals.

Aircraft shapes and relative sizes come from ADS-B Exchange's open-source map
renderer, [tar1090](https://github.com/wiedehopf/tar1090/blob/master/html/markers.js).
The bundled data-only extract is GPL-2.0-or-later; its license is in
`web/vendor/tar1090-LICENSE.txt`. Wikipedia aircraft names automatically match
supported ICAO designators or representative model families in `appearance.js`.
Unknown models retain a dot; multi-aircraft crashes can display two silhouettes.
These are inferred illustrations, not historical transmitted emitter categories or
exact mass/dimension measurements. No crash-data edits or additional update command
are needed: newly extracted aircraft names and fatalities use the same renderer.

