"""Finish all discovered article enrichment, independent of discovery page order."""

import argparse, hashlib, json, threading, time, re, os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse
import requests
from pipeline.extract import (
    ROOT,
    URL,
    STAMP,
    Fetcher,
    reconcile,
    match_episodes,
    parse_civil,
)
from pipeline.articles import article
from pipeline.validate import validate


class Wikimedia:
    def __init__(self, offline=False, refresh=False):
        self.offline = offline
        self.refresh = refresh and not offline
        self.local = threading.local()
        self.lock = threading.Lock()
        self.next_request = 0
        self.cache = ROOT / "cache"
        self.cache.mkdir(exist_ok=True)
        self.current_revisions = {}

    def request(self, params, refresh=False):
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        path = self.cache / ("api-" + key + ".json")
        if path.exists() and not (self.refresh or refresh):
            return json.loads(path.read_text())
        if self.offline:
            raise RuntimeError("Not cached")
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
            self.local.session.headers["User-Agent"] = os.environ.get(
                "WIKIMEDIA_USER_AGENT",
                "AviationCrashAtlas/0.3 (source archive; https://github.com/alexsky2)",
            )
        for attempt in range(4):
            with self.lock:
                delay = max(0, self.next_request - time.monotonic())
                self.next_request = max(time.monotonic(), self.next_request) + 1.0
            time.sleep(delay)
            try:
                response = self.local.session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=dict(params, format="json", maxlag=5),
                    timeout=45,
                )
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    raise RuntimeError(data["error"].get("info", "API error"))
                path.write_text(json.dumps(data))
                return data
            except (requests.RequestException, ValueError, RuntimeError):
                if attempt == 3:
                    raise
                time.sleep(min(30, 2**attempt))

    def prime(self, titles):
        if self.offline:
            return
        titles = sorted(set(titles))
        for start in range(0, len(titles), 40):
            group = titles[start : start + 40]
            result = self.request(
                {
                    "action": "query",
                    "titles": "|".join(t.replace("_", " ") for t in group),
                    "redirects": 1,
                    "prop": "info",
                },
                refresh=True,
            )
            query = result.get("query", {})
            pages = {
                p.get("title", "").replace(" ", "_"): p
                for p in query.get("pages", {}).values()
            }
            aliases = {
                a["from"].replace(" ", "_"): a["to"].replace(" ", "_")
                for a in query.get("redirects", [])
            }
            for title in group:
                canonical = title.replace(" ", "_")
                for _ in range(8):
                    if canonical not in aliases:
                        break
                    canonical = aliases[canonical]
                revision = pages.get(canonical, {}).get("lastrevid")
                if revision:
                    self.current_revisions[title.replace(" ", "_")] = revision
                    self.current_revisions[canonical] = revision

    def fetch(self, title, depth=0):
        if depth > 8:
            raise RuntimeError("Redirect chain exceeds eight pages")
        path = self.cache / (hashlib.sha256(title.encode()).hexdigest() + ".json")
        if not path.exists() and self.offline:
            # Build redirect identities once, under the lock. Other workers must
            # not observe a partially populated index and report cached aliases missing.
            with self.lock:
                if not hasattr(self, "canonical_cache"):
                    identities = {}
                    for candidate in self.cache.glob("*.json"):
                        if candidate.name.startswith("api-"):
                            continue
                        entry = json.loads(candidate.read_text())
                        canonical = entry.get("canonical_title")
                        if canonical:
                            identities[canonical.replace(" ", "_")] = candidate
                    self.canonical_cache = identities
            alias_path = self.canonical_cache.get(title.replace(" ", "_"))
            if alias_path:
                path.write_text(alias_path.read_text())
        cached = json.loads(path.read_text()) if path.exists() else None
        latest = self.current_revisions.get(title.replace(" ", "_"))
        stale = bool(cached and latest and cached["revision"] != latest)
        if cached and not self.refresh and not stale:
            redirect = re.search(
                r'class="redirectText"[^>]*>.*?href="/wiki/([^"#]+)',
                cached["html"],
                re.S,
            )
            if redirect:
                target = unquote(redirect[1])
                resolved = dict(self.fetch(target, depth + 1))
                resolved.setdefault("canonical_title", target)
                path.write_text(json.dumps(resolved))
                return resolved
            return cached
        d = self.request(
            {
                "action": "parse",
                "page": title.replace("_", " "),
                "prop": "text|revid|displaytitle",
                "redirects": 1,
            },
            refresh=stale,
        )["parse"]
        result = {
            "html": d["text"]["*"],
            "revision": d.get("revid"),
            "retrieved_at": STAMP(),
            "canonical_title": d.get("title", title).replace(" ", "_"),
        }
        path.write_text(json.dumps(result))
        canonical_path = self.cache / (
            hashlib.sha256(result["canonical_title"].encode()).hexdigest() + ".json"
        )
        if canonical_path != path:
            canonical_path.write_text(json.dumps(result))
        return result


def titles_from_records(records):
    titles = set()
    for f in records:
        p = f["properties"]
        titles.update(p.get("article_titles", []))
        for source in p["sources"]:
            u = urlparse(source["url"])
            if u.hostname == "en.wikipedia.org" and u.path.startswith("/wiki/"):
                t = unquote(u.path[6:])
                if not t.startswith("List_") and ":" not in t:
                    titles.add(t)
    return {
        t.replace(" ", "_")
        for t in titles
        if ":" not in t and not t.startswith("List_")
    }


def apply_reviewed_locations(records):
    """Apply explicit, user-authorized location corrections after article parsing."""
    corrections = json.loads((ROOT / 'pipeline/reviewed.json').read_text())
    by_article = {item['article_url']: item for item in corrections}
    for record in records:
        props = record['properties']
        correction = by_article.get(props.get('article_url'))
        if correction:
            record['geometry'] = correction['geometry']
            props['site_geometries'] = [correction['geometry']]
            for field in ['location_kind', 'location_quality', 'uncertainty', 'evidence']:
                props[field] = correction[field]
            props['override_location'] = True


def publish(records, report):
    apply_reviewed_locations(records)
    excluded = [r for r in records if r['properties']['civil_or_military'] == 'military']
    records = [r for r in records if r['properties']['civil_or_military'] == 'civil']
    excluded_ids = sorted(set(report.get('publication_scope', {}).get('excluded_source_entry_ids', [])) | {e['entry_id'] for r in excluded for e in r['properties'].get('source_entries', [])})
    published_ids = {e['entry_id'] for r in records for e in r['properties'].get('source_entries', [])}
    excluded_ids = sorted(set(excluded_ids) - published_ids)
    report['publication_scope'] = {'categories': ['civil'], 'excluded_military_records': len(excluded), 'excluded_source_entry_ids': excluded_ids}
    for record in records:
        p = record["properties"]
        if re.search(
            r"near[ -](?:crash|miss|collision)|narrowly (?:avoided|missed)",
            p["name"] + " " + p["description"],
            re.I,
        ):
            p["event_type"] = "incident"
            if record["geometry"]:
                p["location_kind"] = "event site"
    validate(records)
    from pipeline.audit import audit, write_report
    entry_audit = audit(records, Fetcher(offline=True), report.get("enrichment"), excluded_records=excluded, excluded_entry_ids=excluded_ids)
    write_report(entry_audit, ROOT / "web/data")
    report["source_entry_audit"] = entry_audit["summary"]
    mapped = [r for r in records if r["geometry"]]
    countries = Counter(r["properties"]["state"] for r in mapped)
    metadata = {
        "schema_version": 2,
        "generated_at": STAMP(),
        "total": len(records),
        "mapped": len(mapped),
        "unlocated": len(records) - len(mapped),
        "approximate": sum(
            r["properties"]["location_quality"] == "approximate" for r in records
        ),
        "coverage_complete": False,
        "mapped_by_country": dict(countries),
        "with_images": sum(bool(r["properties"].get("images")) for r in records),
        "license": "Wikipedia text: CC BY-SA 4.0; images retain individual file licenses",
        "scope": "Wikipedia list entries and available accident articles; source-entry audit reports unresolved coverage and list-only crash locations",
    }
    report.update(metadata)
    report["awaiting_review"] = sum(
        r["properties"].get("review_status") != "reviewed" for r in records
    )
    for source in report.get("sources", {}).values():
        if source.get("status") != "failed":
            source.pop("error", None)
    out = ROOT / "web/data"
    old = out / "events.geojson"
    if old.exists():
        (out / "events.previous.geojson").write_text(old.read_text())
    for name, payload in [
        (
            "events.geojson",
            {"type": "FeatureCollection", "metadata": metadata, "features": records},
        ),
        (
            "events.json",
            {
                "metadata": metadata,
                "events": [
                    dict(r["properties"], geometry=r["geometry"]) for r in records
                ],
            },
        ),
        ("coverage.json", report),
    ]:
        temporary = out / (name + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
        temporary.replace(out / name)
    print(json.dumps(metadata), flush=True)


def main(argv=None, records=None, report=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    if records is None:
        data = json.loads((ROOT / "web/data/events.geojson").read_text())
        records = data["features"]
    if report is None:
        report = json.loads((ROOT / "web/data/coverage.json").read_text())
    titles = sorted(
        titles_from_records(records)
        | {
            t
            for t, source in report.get("sources", {}).items()
            if source.get("family") == "event article"
        }
    )
    wiki = Wikimedia(args.offline, args.refresh)
    fallback = {}
    for r in records:
        for t in r["properties"].get("article_titles", []):
            fallback.setdefault(t.replace(" ", "_"), r["properties"]["date"])
    fetched = []
    failures = {}
    metadata = {}
    print(
        f"Enriching all {len(titles)} discovered articles; {args.workers} workers; global maximum 1 request/second.",
        flush=True,
    )
    # Batch images and redirect identities. Generic page coordinates are never copied to events.
    for start in range(0, len(titles), 40):
        group = titles[start : start + 40]
        try:
            result = wiki.request(
                {
                    "action": "query",
                    "titles": "|".join(t.replace("_", " ") for t in group),
                    "redirects": 1,
                    "prop": "pageimages|info",
                    "piprop": "thumbnail|name|original",
                    "pithumbsize": 640,
                },
                refresh=not args.offline,
            )
            pages = result.get("query", {}).get("pages", {})
            bytitle = {p.get("title", "").replace(" ", "_"): p for p in pages.values()}
            aliases = {
                a["from"].replace(" ", "_"): a["to"].replace(" ", "_")
                for a in result.get("query", {}).get("redirects", [])
            }
            for t in group:
                canonical = t
                for _ in range(8):
                    if canonical not in aliases:
                        break
                    canonical = aliases[canonical]
                metadata[t] = bytitle.get(canonical, {})
                revision = metadata[t].get("lastrevid")
                if revision:
                    wiki.current_revisions[t] = revision
                    wiki.current_revisions[canonical] = revision
        except Exception as exc:
            print(f"Image batch {start}: {exc}", flush=True)

    def process(title):
        page = wiki.fetch(title)
        canonical = page.get("canonical_title", title)
        source = {
            "url": URL(canonical),
            "title": title.replace("_", " "),
            "kind": "Wikipedia",
            "revision": page["revision"],
            "retrieved_at": page["retrieved_at"],
        }
        record = article(page["html"], canonical, source, fallback.get(title))
        if record:
            record["properties"]["article_titles"] = list(
                dict.fromkeys([title, canonical])
            )
        return title, record, page

    with ThreadPoolExecutor(max_workers=min(4, max(1, args.workers))) as pool:
        jobs = {pool.submit(process, t): t for t in titles}
        for i, future in enumerate(as_completed(jobs), 1):
            title = jobs[future]
            try:
                _, record, page = future.result()
                report.setdefault("sources", {}).setdefault(title, {}).update(
                    status="parsed" if record else "needs review",
                    family="event article",
                    revision=page["revision"],
                    retrieved_at=page["retrieved_at"],
                )
                if record:
                    image = metadata.get(title, {})
                    if image.get("thumbnail") and image.get("pageimage"):
                        url = "https://en.wikipedia.org/wiki/File:" + image[
                            "pageimage"
                        ].replace(" ", "_")
                        existing = next(
                            (
                                img
                                for img in record["properties"]["images"]
                                if unquote(img["url"]) == unquote(url)
                            ),
                            None,
                        )
                        if existing:
                            existing["thumbnail"] = image["thumbnail"]["source"]
                        else:
                            record["properties"]["images"].insert(
                                0,
                                {
                                    "url": url,
                                    "thumbnail": image["thumbnail"]["source"],
                                    "caption": image["pageimage"].replace("_", " "),
                                    "kind": "article illustration",
                                    "source_url": URL(title),
                                    "revision": page["revision"],
                                },
                            )
                    fetched.append(record)
            except Exception as exc:
                failures[title] = str(exc)
                report.setdefault("sources", {}).setdefault(title, {}).update(
                    status="failed", error=str(exc), family="event article"
                )
            if i % 50 == 0 or i == len(titles):
                print(
                    f'{i}/{len(titles)} articles · {sum(r["geometry"] is not None for r in fetched)} site coordinate records · {len(failures)} failures',
                    flush=True,
                )
    # Dedicated articles lead the merge so dates, aircraft, and site evidence replace shallow list parsing.
    combined = reconcile(fetched + records)
    try:
        match_episodes(combined, Fetcher(offline=True).fetch("List_of_Mayday_episodes"))
    except RuntimeError:
        pass
    report["enrichment"] = {
        "discovered_articles": len(titles),
        "processed_articles": len(titles) - len(failures),
        "failures": failures,
        "completed_at": STAMP(),
    }
    publish(combined, report)


if __name__ == "__main__":
    main()
