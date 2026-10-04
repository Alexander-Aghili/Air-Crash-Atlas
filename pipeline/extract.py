"""Cached Wikipedia discovery; coordinates only from event article infoboxes."""

import argparse, hashlib, json, re, time, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
INDEX = "List_of_accidents_and_incidents_involving_military_aircraft"
SEEDS = [
    "List_of_accidents_and_incidents_involving_commercial_aircraft",
]


def is_accident_list(title):
    """Select aviation lists, including aircraft-model and air-show sublists."""
    lower = title.lower()
    return title.startswith("List_") and "military" not in lower and bool(
        re.search(r"accident|incident|crash|losses|shootdown", lower)
        and re.search(r"aircraft|airliner|airline|aviation|flight|helicopter|aerial|air_show|air_force|military|boeing|airbus|douglas|lockheed|harrier|lightning|(?:^|_)[fbc]-\d", lower)
    )


STAMP = lambda: datetime.now(timezone.utc).isoformat()
URL = lambda title: "https://en.wikipedia.org/wiki/" + quote(
    title.replace(" ", "_"), safe="_,()"
)


def event(title, date, text, source, locator="", category="civil", aircraft=None):
    identity = (
        date
        + "|"
        + title
        + "|"
        + "|".join(sorted(a.get("registration", "") for a in (aircraft or [])))
    )
    eid = hashlib.sha256(identity.encode()).hexdigest()[:20]
    from pipeline.source_entries import source_entry
    source_entries = [source_entry(source, text)] if unquote(source["url"]).split("/wiki/")[-1].startswith("List_") else []
    lower = (title + " " + text).lower()
    # Type classification is provisional until reviewed.

    kind = "crash"
    if re.search(
        r"near[ -](?:crash|miss|collision)|narrowly (?:avoided|missed)", lower
    ):
        kind = "incident"
    elif re.search(r"collision|collided", lower):
        kind = "collision"
    elif "shot down" in lower:
        kind = "combat loss"
    elif re.search(
        r"(aircraft|plane|flight) (?:\w+ ){0,3}(disappeared|went missing)|vanished without",
        lower,
    ):
        kind = "disappearance"
    elif re.search(r"destroyed on the ground|parked aircraft|ground collision", lower):
        kind = "ground incident"
    elif re.search(r"hijack|emergency landing|diverted", lower) and not re.search(
        r"crash|destroyed|fatal", lower
    ):
        kind = "incident"
    return {
        "type": "Feature",
        "id": eid,
        "geometry": None,
        "properties": {
            "event_id": eid,
            "name": title,
            "title": title,
            "date": date,
            "date_precision": "day" if len(date) == 10 else "month" if len(date) == 7 else "year",
            "event_type": kind,
            "civil_or_military": category,
            "aircraft": aircraft or [],
            "state": "Unknown",
            "location_text": "Location awaiting review",
            "location_kind": "unknown",
            "location_quality": "missing",
            "uncertainty": None,
            "evidence": {"method": "No event-specific impact coordinates established"},
            "sources": [source],
            "source_entries": source_entries,
            "category_evidence": {"method": "source list context", "priority": 1},
            "source_url": source["url"],
            "source_locator": locator,
            "description": text,
            "media": [],
            "review_status": "needs review",
        },
    }


def references(node, soup):
    links = []
    index = soup.__dict__.get("reference_index")
    if index is None:
        index = {item["id"]: item for item in soup.find_all("li", id=True)}
        soup.__dict__["reference_index"] = index
    for a in node.select('sup a[href^="#"]'):
        ref = index.get(unquote(a["href"][1:]))
        if not ref:
            continue
        for link in ref.select('a[href^="https://"],a[href^="http://"]'):
            if "wikipedia.org" in link["href"]:
                continue
            source = {
                "url": link["href"],
                "title": link.get_text(" ", strip=True),
                "kind": "Reference (unreviewed lead)",
            }
            if source not in links:
                links.append(source)
    return links


def parse_list(html, title, source):
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".mw-parser-output") or soup
    year = None
    section = ""
    records = []
    pending_date = None
    for node in content.find_all(["h2", "h3", "dt", "dd"]):
        text = node.get_text(" ", strip=True)
        if node.name in ["h2", "h3"]:
            match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", text)
            if match:
                year = match[1]
            anchor = node.get("id") or (
                node.find(id=True).get("id") if node.find(id=True) else ""
            )
            if anchor:
                section = anchor
        elif node.name == "dt":
            pending_date = text
        elif node.name == "dd" and pending_date and len(text) > 40:
            from pipeline.source_entries import date_text
            date = date_text(pending_date, year)
            if not date:
                continue
            raw_date = pending_date + (" " + year if year and not re.search(r"\b(?:18|19|20)\d{2}\b", pending_date) else "")
            serials = re.findall(r"\b\d{2}-\d{4,6}\b", text)
            types = [
                a.get_text(" ", strip=True)
                for a in node.select("a[href]")
                if re.search(
                    r"(Boeing|Douglas|Lockheed|Focke|Supermarine|Cessna|Sukhoi|MiG|\b[BCFP]-\d|Hawker|Northrop|Airbus|Tupolev|Antonov)",
                    a.get_text(),
                )
            ]
            aircraft = [
                {
                    "type": (
                        types[min(i, len(types) - 1)] if types else "Pending review"
                    ),
                    "registration": serial,
                    "operator": "",
                }
                for i, serial in enumerate(dict.fromkeys(serials))
            ]
            if not aircraft and types:
                aircraft = [
                    {"type": t, "registration": "", "operator": ""}
                    for t in dict.fromkeys(types)
                ]
            link = dict(
                source, url=URL(title) + (("#" + quote(section)) if section else "")
            )
            links = [
                unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
                for a in node.select('a[href^="/wiki/"]')
                if ":" not in unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
                and re.search(
                    r"(Flight_\d|crash|disaster|collision|shootdown|accident)",
                    a["href"],
                    re.I,
                )
                and not a["href"].startswith("/wiki/List_")
                and not re.match(
                    r"/wiki/(File|Image|Category|Template|Wikipedia|Help):", a["href"]
                )
            ]
            name = (
                links[0].replace("_", " ")
                if links
                else f"{raw_date} · "
                + (" / ".join(serials) if serials else text[:85])
            )
            record = event(
                name,
                date,
                text,
                link,
                raw_date + "; " + ", ".join(serials),
                aircraft=aircraft,
                category="military" if "military" in title.lower() else "civil",
            )
            record["properties"]["article_titles"] = links[:1]
            record["properties"]["related_article_titles"] = links[1:]
            record["properties"]["location_text"] = text
            record["properties"]["location_evidence_pending"] = True
            record["properties"]["date_original"] = raw_date
            record["properties"]["sources"].extend(references(node, soup))
            records.append(record)
    return records


def parse_civil(html, title, source):
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".mw-parser-output") or soup
    records = []
    country = "Unknown"
    section = ""
    inherited_year = None
    for node in content.find_all(["h2", "h3", "li"]):
        if node.name in ["h2", "h3"]:
            heading_year = re.fullmatch(
                r"(18\d{2}|19\d{2}|20\d{2})", node.get_text(" ", strip=True)
            )
            if heading_year:
                inherited_year = heading_year[1]
            if "airliners_by_location" in title:
                country = node.get_text(" ", strip=True).replace("[edit]", "").strip()
            section = node.get("id") or (
                node.find(id=True).get("id") if node.find(id=True) else ""
            )
            continue
        if node.find_parent("li") or node.find_parent(class_="reflist"):
            continue
        text = node.get_text(" ", strip=True)
        if len(text) < 40:
            continue
        links = [
            unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
            for a in node.select('a[href^="/wiki/"]')
            if ":" not in unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
            and re.search(
                r"(Flight_\d|crash|disaster|collision|shootdown|accident)",
                a["href"],
                re.I,
            )
            and not a["href"].startswith("/wiki/List_")
            and not re.match(
                r"/wiki/(File|Image|Category|Template|Wikipedia|Help):", a["href"]
            )
        ]
        year = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", text)
        if not links or not (inherited_year or year):
            continue
        date = inherited_year or year[1]
        if inherited_year:
            leading_date = re.match(r"([A-Z][a-z]+ \d{1,2})\s*[–—-]", text)
            if leading_date:
                try:
                    date = datetime.strptime(
                        leading_date[1] + " " + inherited_year, "%B %d %Y"
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        for pattern, fmt in [
            (r"\b(\d{1,2} [A-Z][a-z]+ \d{4})", "%d %B %Y"),
            (r"\b([A-Z][a-z]+ \d{1,2}, \d{4})", "%B %d, %Y"),
        ]:
            match = re.search(pattern, text)
            if match:
                try:
                    date = datetime.strptime(match[1], fmt).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        r = event(
            links[0].replace("_", " "),
            date,
            text,
            dict(source, url=URL(title) + (("#" + quote(section)) if section else "")),
            category="civil",
        )
        r["properties"].update(
            article_titles=links[:1],
            related_article_titles=links[1:],
            state=country,
            location_text=text,
            source_locator=text[:120],
        )
        r["properties"]["sources"].extend(references(node, soup))
        records.append(r)
    return records


class Fetcher:
    def __init__(self, offline=False, refresh=False):
        self.offline, self.refresh = offline, refresh
        self.client = None

    def prime(self, titles):
        if self.client is None:
            from pipeline.enrich import Wikimedia

            self.client = Wikimedia(self.offline, self.refresh)
        self.client.prime(titles)

    def fetch(self, title):
        if self.client is None:
            from pipeline.enrich import Wikimedia

            self.client = Wikimedia(self.offline, self.refresh)
        return self.client.fetch(title)


from pipeline.articles import article


def reconcile(records):
    result = []
    seen = {}
    by_name = {}
    by_source = {}
    by_article = {}
    for record in records:
        p = record["properties"]
        serials = tuple(
            sorted(a["registration"] for a in p["aircraft"] if a.get("registration"))
        )
        key = (p["date"], serials or p["name"].lower())
        existing = seen.get(key) or by_name.get((p["date"], p["name"].lower()))
        if not existing:
            year = p["date"][:4]
            candidates = [
                by_source.get((year, URL(t))) or by_article.get((year, URL(t)))
                for t in p.get("article_titles", [])
            ]
            candidates.append(by_article.get((year, p["source_url"].split("#")[0])))
            existing = next((r for r in candidates if r is not None), None)
        if existing:
            ep = existing["properties"]
            for source in p["sources"]:
                same = next(
                    (old for old in ep["sources"] if old["url"] == source["url"]), None
                )
                if same:
                    for field in ["revision", "retrieved_at"]:
                        if source.get(field):
                            same[field] = source[field]
                else:
                    ep["sources"].append(source)
            candidate_priority = p.get("category_evidence", {}).get("priority", 0)
            existing_priority = ep.get("category_evidence", {}).get("priority", 0)
            if candidate_priority > existing_priority or (candidate_priority == existing_priority <= 1 and p["civil_or_military"] == "military"):
                ep["civil_or_military"] = p["civil_or_military"]
                ep["category_evidence"] = p["category_evidence"]
            entry_ids = {entry["entry_id"] for entry in ep.get("source_entries", [])}
            ep.setdefault("source_entries", []).extend(entry for entry in p.get("source_entries", []) if entry["entry_id"] not in entry_ids)
            ep["article_titles"] = list(dict.fromkeys(ep.get("article_titles", []) + p.get("article_titles", [])))
            if ep["state"] == "Unknown" and p["state"] != "Unknown":
                ep["state"] = p["state"]
            if not ep["description"]:
                ep["description"] = p["description"]
            if not ep["source_locator"]:
                ep["source_locator"] = p["source_locator"]
            if (
                not existing["geometry"]
                and "raw_infobox" not in ep
                and record["geometry"]
                and not ep.get("override_location")
            ):
                existing["geometry"] = record["geometry"]
                for field in [
                    "location_text",
                    "location_kind",
                    "location_quality",
                    "evidence",
                ]:
                    ep[field] = p[field]
                if p["state"] != "Unknown":
                    ep["state"] = p["state"]
            if not ep["aircraft"]:
                ep["aircraft"] = p["aircraft"]
            if p["source_url"].split("#")[0] in [
                URL(t) for t in ep.get("article_titles", [])
            ]:
                ep["source_url"] = p["source_url"]
                ep["name"] = p["name"]
                ep["title"] = p["title"]
                if p["aircraft"]:
                    ep["aircraft"] = p["aircraft"]
            if len(ep["date"]) < len(p["date"]):
                ep["date"] = p["date"]
                ep["date_precision"] = p["date_precision"]
            ep["media"].extend(m for m in p["media"] if m not in ep["media"])
            ep.setdefault("images", []).extend(
                img
                for img in p.get("images", [])
                if not any(old["url"] == img["url"] for old in ep.get("images", []))
            )
            for field in [
                "occurrence_type",
                "participating_categories",
                "raw_infobox",
                "search_aliases",
                "site_geometries",
                "article_url",
                "fatalities",
                "occupants",
                "survivors",
                "location_sources",
            ]:
                if field in p and (field not in ep or ep[field] is None or ep[field] == ""):
                    ep[field] = p[field]
        else:
            result.append(record)
            existing = record
        ep = existing["properties"]
        seen.setdefault(key, existing)
        by_name.setdefault((ep["date"], ep["name"].lower()), existing)
        by_source.setdefault((ep["date"][:4], ep["source_url"].split("#")[0]), existing)
        for title in ep.get("article_titles", []):
            by_article.setdefault((ep["date"][:4], URL(title)), existing)
        for title in p.get("article_titles", []):
            by_article.setdefault((ep["date"][:4], URL(title)), existing)
    return result


def match_episodes(records, data):
    soup = BeautifulSoup(data["html"], "lxml")
    matches = {}
    section = ""
    for node in soup.find_all(["h2", "h3", "tr"]):
        if node.name in ["h2", "h3"]:
            section = node.get("id") or (
                node.find(id=True).get("id") if node.find(id=True) else ""
            )
            continue
        cells = node.find_all(["td", "th"], recursive=False)
        if len(cells) < 4:
            continue
        title = cells[2].get_text(" ", strip=True)
        if not title.startswith(('"', "“")):
            continue
        for a in node.select('a[href^="/wiki/"]'):
            subject = unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
            matches.setdefault(URL(subject), []).append(
                {
                    "kind": "episode",
                    "provider": "Mayday / Air Crash Investigation",
                    "title": title.strip('"“”'),
                    "edition": "Wikipedia episode listing",
                    "episode": cells[1].get_text(" ", strip=True),
                    "url": URL("List_of_Mayday_episodes")
                    + (("#" + quote(section)) if section else ""),
                    "match_evidence": "Episode row explicitly links the event article",
                    "revision": data["revision"],
                    "retrieved_at": data["retrieved_at"],
                }
            )
    count = 0
    for record in records:
        p = record["properties"]
        urls = {s["url"].split("#")[0] for s in p["sources"]} | {
            URL(t) for t in p.get("article_titles", [])
        }
        for url in urls:
            for media in matches.get(url, []):
                if media not in p["media"]:
                    p["media"].append(media)
                    count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-pages", type=int, default=0)
    args = parser.parse_args(argv)
    fetcher = Fetcher(args.offline, args.refresh)
    previous_report = ROOT / "web/data/coverage.json"
    known_lists = []
    if previous_report.exists():
        known_lists = [
            t
            for t in json.loads(previous_report.read_text()).get("sources", {})
            if t.startswith("List_")
        ]
    try:
        fetcher.prime(SEEDS + known_lists)
    except Exception as exc:
        print(
            f"Revision check unavailable: {exc}; continuing with cached sources",
            flush=True,
        )
    inventory = {
        t: {"status": "pending", "family": "discovery"}
        for t in SEEDS
    }
    queue = list(inventory)
    records = []
    processed = 0
    while queue and (not args.max_pages or processed < args.max_pages):
        title = queue.pop(0)
        processed += 1
        if processed % 25 == 0:
            print(
                f"Processed {processed} source pages; {len(queue)} queued", flush=True
            )
        try:
            data = fetcher.fetch(title)
            inventory[title].update(
                status="fetched",
                revision=data["revision"],
                retrieved_at=data["retrieved_at"],
            )
            source = {
                "url": URL(title),
                "title": title.replace("_", " "),
                "kind": "Wikipedia",
                "revision": data["revision"],
                "retrieved_at": data["retrieved_at"],
            }
            if not title.startswith("List_"):
                item = article(data["html"], title, source)
                items = [item] if item else []
            else:
                from pipeline.lists import parse_flexible

                items = parse_list(data["html"], title, source) + parse_flexible(
                    data["html"], title, source
                )
                if "airliner" in title or "commercial" in title:
                    items += parse_civil(data["html"], title, source)
            from pipeline.source_entries import parse_unusual
            if title.startswith("List_"):
                items += parse_unusual(data["html"], title, source, items)
            records.extend(items)
            soup = BeautifulSoup(data["html"], "lxml")
            for a in soup.select('a[href^="/wiki/"]'):
                linked = unquote(a["href"].split("/wiki/", 1)[1]).split("#")[0]
                discover = is_accident_list(linked)
                if discover and linked not in inventory:
                    inventory[linked] = {
                        "status": "pending",
                        "family": "aviation lists",
                    }
                    queue.append(linked)
            for item in items:
                for linked in item["properties"].get("article_titles", []):
                    if linked not in inventory:
                        inventory[linked] = {
                            "status": "pending",
                            "family": "event article",
                        }
            inventory[title].update(
                status="parsed" if items or title == INDEX else "needs review",
                events=len(items),
            )
        except Exception as exc:
            inventory[title].update(
                status=(
                    "pending" if args.offline and str(exc) == "Not cached" else "failed"
                ),
                error=str(exc),
            )
    records = reconcile(records)
    try:
        episode_data = fetcher.fetch("List_of_Mayday_episodes")
        match_episodes(records, episode_data)
        inventory["List_of_Mayday_episodes"] = {"status": "parsed", "family": "episode metadata"}
    except RuntimeError:
        pass
    report = {
        "sources": inventory,
        "extracted": sum(s.get("events", 0) for s in inventory.values()),
    }
    from pipeline.enrich import main as enrich, publish

    if args.max_pages:
        publish(records, report)
    else:
        options = ["--offline"] if args.offline else []
        if args.refresh:
            options.append("--refresh")
        enrich(options, records=records, report=report)


if __name__ == "__main__":
    main()
