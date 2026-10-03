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

Event details come from Wikipedia lists and accident articles. No manually reviewed records, date overrides, previous published records, or external wreck-site coordinates are injected. Article records retain raw infobox text alongside normalized fields. Discovery follows linked aviation accident lists recursively, starting with the two military and commercial accident lists. This does not guarantee every Wikipedia crash is discovered or parsed.

The archive is still incomplete: list-only events require further location evidence, unsupported list layouts need review, and automatic event and country classification remains provisional. Completing the discovered article pass does not imply complete worldwide coverage. No coordinates are invented to increase marker counts.

## Images and sources

Images come from accident articles and Wikipedia PageImages metadata. They may depict the aircraft, aftermath, or site maps, as indicated by captions. Cards link directly to Wikipedia and available image file pages; detail panels show images and provenance. Wikimedia file pages provide authors and individual licenses. Wikipedia text is reused under CC BY-SA 4.0; revision IDs and retrieval dates are retained.

Mayday matches require an episode row linking the event article. Media links are informational, not promises of streaming availability. No hand-authored event records are injected during refresh.

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


Commercial and Military switches independently control both the map and record list. Both start enabled; saved URLs retain disabled groups, and Reset enables both. Commercial corresponds to records classified as civil in the archive.

## Source-entry audit

Every publication runs a source-entry audit against its cached source snapshots. Run `python3 -m pipeline.audit` to fetch unavailable source pages and audit again (or `--offline` to stay in cache). Use `--repair` to extract supported entries missing an exact provenance link; new dedicated articles can then be enriched with `python3 -m pipeline.enrich`. Open `web/data/audit.html` for the readable report; `audit.json` retains every candidate entry, its raw text, source revision, matching event IDs, and unresolved reason. The audit walks from the two source roots independently of extraction and only certifies matches through exact source-entry provenance. It flags disagreement between source-entry dates and record dates, and reports unavailable article enrichment separately. Related accident links are retained as related links and never used to merge two event identities. Missing coordinates are counted separately from missing records. Unavailable pages, unrecognized layouts, and compound narratives remain explicit gaps. A matching overall record count does not certify coverage.

The supplemental parser handles full dates in definition lists, narrative paragraphs, nested loss bullets, date-column aliases, multirow table headings, and inherited table cells. Month-only dates retain month precision. The original source text remains attached through duplicate merging; article operator evidence takes priority over shallow list classification.
