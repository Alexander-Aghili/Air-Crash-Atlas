"""Audit raw source entries against published record provenance, not aggregate counts."""
import argparse
from collections import Counter, defaultdict, deque
from html import escape
import json
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup
from pipeline.extract import ROOT, SEEDS, URL, STAMP, Fetcher, is_accident_list
from pipeline.source_entries import enumerate_entries


def audit(records, fetcher, enrichment=None):
    by_entry = defaultdict(list)
    article_dates = defaultdict(set)
    for record in records:
        if record["properties"].get("article_url"):
            for title in record["properties"].get("article_titles", []):
                article_dates[title.replace(" ", "_")].add(record["properties"]["date"])
        for entry in record['properties'].get('source_entries', []):
            by_entry[entry['entry_id']].append(record)
    queue = deque((title, None) for title in SEEDS)
    seen, pages, entries = set(), [], []
    while queue:
        title, parent = queue.popleft()
        if title in seen:
            continue
        seen.add(title)
        if len(seen) % 20 == 0:
            print(f"Auditing {len(seen)} source pages; {len(queue)} links queued", flush=True)
        page = {'title': title, 'url': URL(title), 'discovered_from': parent}
        try:
            data = fetcher.fetch(title)
        except Exception as exc:
            page.update(status='unavailable', error=str(exc), entries=None)
            pages.append(page)
            continue
        soup = BeautifulSoup(data['html'], 'lxml')
        content = soup.select_one('.mw-parser-output') or soup
        # The audit independently walks the graph from the two roots.
        child_lists = set()
        for link in content.select('a[href^="/wiki/"]'):
            linked = unquote(link['href'][6:]).split('#')[0]
            if is_accident_list(linked):
                child_lists.add(linked)
                if linked not in seen:
                    queue.append((linked, title))
        candidates = enumerate_entries(data['html'], title)
        canonical = data.get('canonical_title', title)
        if canonical != title:
            # Aliases are inventoried once, retaining the discovery edge.
            page['canonical_title'] = canonical
        counts = Counter()
        for candidate in candidates:
            entry = {key: value for key, value in candidate.items() if not key.startswith('_')}
            entry.update(source_title=title, source_url=URL(title) + ('#' + candidate['section'] if candidate['section'] else ''), revision=data['revision'])
            matched = by_entry.get(candidate['entry_id'], [])
            dated_matches = [r for r in matched if candidate['date'] and r['properties']['date'].startswith(candidate['date'])]
            if dated_matches:
                matched = dated_matches
            # Exact normalized source text is the only automatic coverage proof.
            if matched:
                entry['status'] = 'matched'
                entry['event_ids'] = sorted({r['id'] for r in matched})
                entry['mapped'] = any(r['geometry'] is not None for r in matched)
                entry['article_enriched'] = any(r['properties'].get('article_url') for r in matched)
                entry['record_names'] = sorted({r['properties']['name'] for r in matched})
                entry['types'] = sorted({r['properties']['event_type'] for r in matched})
                entry['categories'] = sorted({r['properties']['civil_or_military'] for r in matched})
                if candidate['date'] and not any(r['properties']['date'].startswith(candidate['date']) for r in matched):
                    entry['status'] = 'needs_review'
                    entry['reason'] = 'source_date_disagrees_with_record_or_precision_was_lost'
                    entry['record_dates'] = sorted({r['properties']['date'] for r in matched})
                for record in matched:
                    props = record['properties']
                    if props.get('article_url'):
                        continue
                    for linked_title in props.get('article_titles', []):
                        known_dates = article_dates.get(linked_title.replace(' ', '_'), set())
                        if known_dates and candidate['date'] and not any(date[:4] == candidate['date'][:4] for date in known_dates):
                            entry['status'] = 'needs_review'
                            entry['reason'] = 'linked_article_describes_a_different_event_year; event subject needs verification'
                            entry['linked_article_dates'] = sorted(known_dates)
                if candidate['review_reason']:
                    entry['status'] = 'needs_review'
                    entry['reason'] = candidate['review_reason'] + '; published record exists but this entry is not certified'
                if not entry['mapped']:
                    entry['location_reasons'] = sorted({r['properties'].get('evidence', {}).get('method', 'No crash-site coordinates') for r in matched})
            else:
                entry['status'] = 'needs_review' if candidate['review_reason'] else 'missing'
                entry['reason'] = candidate['review_reason'] or 'Source entry has no exact provenance link to a published record'
            counts[entry['status']] += 1
            entries.append(entry)
        page.update(status='scanned', revision=data['revision'], retrieved_at=data['retrieved_at'], entries=len(candidates), counts=dict(counts), layouts=dict(Counter(e['layout'] for e in candidates)))
        if not candidates and child_lists and not content.find('dd') and not content.select('table.wikitable'):
            page['status'] = 'index'
        elif not candidates:
            page['review_reason'] = 'No event candidates recognized; may be an index/redirect or an unsupported layout. Not certified complete.'
        pages.append(page)
    totals = Counter({'matched': 0, 'missing': 0, 'needs_review': 0})
    totals.update(e['status'] for e in entries)
    unmatched_pages = [p for p in pages if p['status'] == 'unavailable' or (p.get('entries') == 0 and p['status'] != 'index' and 'canonical_title' not in p)]
    linked_ids = {eid for entry in entries if entry['status'] == 'matched' for eid in entry['event_ids']}
    return {'generated_at': STAMP(), 'roots': [URL(t) for t in SEEDS],
            'scope': 'Dated and event-like entries in recursively linked aviation lists from the two roots, at the recorded Wikipedia revisions. Candidate scanning is conservative, not a claim that every possible prose layout is understood.',
            'coverage_complete': False,
            'article_enrichment': enrichment or {},
            'summary': {'article_enrichment_failures': len((enrichment or {}).get('failures', {})), 'source_pages': len(pages), 'unavailable_pages': sum(p['status'] == 'unavailable' for p in pages), 'pages_requiring_review': len(unmatched_pages), 'candidate_entries': len(entries), 'entries_with_published_record': sum(bool(e.get('event_ids')) for e in entries), 'entries_without_published_record': sum(not e.get('event_ids') for e in entries), **dict(totals), 'matched_entries_without_article_enrichment': sum(e['status'] == 'matched' and not e['article_enriched'] for e in entries), 'matched_entries_without_coordinates': sum(e['status'] == 'matched' and not e['mapped'] for e in entries), 'unique_records_linked_to_entries': len(linked_ids), 'published_records': len(records), 'published_records_without_entry_link_in_audited_scope': len(records) - len(linked_ids)},
            'pages': pages, 'entries': entries}


def write_report(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    summary = report['summary']
    rows = ''.join('<tr><td><a href="' + escape(p['url'], quote=True) + '">' + escape(p['title'].replace('_', ' ')) + '</a></td><td>' + escape(p['status']) + '</td><td>' + str(p.get('entries', '—')) + '</td><td>' + str(p.get('counts', {}).get('matched', 0)) + '</td><td>' + str(p.get('counts', {}).get('missing', 0)) + '</td><td>' + str(p.get('counts', {}).get('needs_review', 0)) + '</td><td>' + escape(p.get('error', p.get('review_reason', ''))) + '</td></tr>' for p in report['pages'])
    issues = ''.join('<details><summary>' + escape(e['status'] + ': ' + e['source_title'].replace('_', ' ') + ' — ' + e['text'][:110]) + '</summary><p>' + escape(e.get('reason', '')) + '</p><p>' + escape(e['text']) + '</p><a href="' + escape(e['source_url'], quote=True) + '">Wikipedia source</a><p>Entry ID: ' + e['entry_id'] + '</p></details>' for e in report['entries'] if e['status'] != 'matched')
    article_gaps = ''.join('<li><a href="' + escape(URL(title), quote=True) + '">' + escape(title.replace('_', ' ')) + '</a>: ' + escape(reason) + '</li>' for title, reason in report.get('article_enrichment', {}).get('failures', {}).items())
    html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Wikipedia source-entry audit</title><style>body{font:16px system-ui;max-width:1300px;margin:32px auto;padding:0 20px;color:#182c3c}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}details{padding:10px;border-bottom:1px solid #ddd}a{color:#1260a0}summary{cursor:pointer}li{margin:6px 0}</style><h1>Wikipedia source-entry audit</h1><p>Coverage is incomplete. Counts measure source entries, not unique crashes. Several entries can describe the same crash; a missing marker does not mean a missing record.</p><p>' + escape(report['scope']) + '</p><p>Generated: ' + escape(report['generated_at']) + '</p><ul>' + ''.join('<li>' + escape(key.replace('_', ' ')) + ': <strong>' + str(value) + '</strong></li>' for key, value in summary.items()) + '</ul><p><a href="audit.json">Full machine-readable audit, including every matched and unmatched entry</a></p><h2>Source pages</h2><table><thead><tr><th>Source</th><th>Status</th><th>Candidates</th><th>Matched</th><th>Missing</th><th>Review</th><th>Reason</th></tr></thead><tbody>' + rows + '</tbody></table><h2>Entries requiring review</h2>' + issues + '<h2>Article fetch and enrichment gaps</h2><p>A source-list record can be present even when its linked article has not been fetched or enriched. These failures affect article details and potentially coordinates; they do not automatically mean the event is missing.</p><ul>' + article_gaps + '</ul></html>'
    (output / 'audit.html').write_text(html)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--repair', action='store_true', help='Extract supported source entries missing from the published dataset, then rerun the audit')
    args = parser.parse_args(argv)
    records = json.loads((ROOT / 'web/data/events.geojson').read_text())['features']
    coverage_path = ROOT / 'web/data/coverage.json'
    coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}
    report = audit(records, Fetcher(args.offline, args.refresh), coverage.get('enrichment'))
    if args.repair:
        from pipeline.source_entries import parse_unusual
        from pipeline.extract import reconcile
        from pipeline.enrich import publish
        fetcher = Fetcher(offline=True)
        additional = []
        # Upgrade coarse dates only when all more-precise source entries agree.
        by_id = {record['id']: record for record in records}
        date_candidates = defaultdict(set)
        for entry in report['entries']:
            if not entry['date'] or entry.get('review_reason'):
                continue
            for event_id in entry.get('event_ids', []):
                old_date = by_id[event_id]['properties']['date']
                if len(entry['date']) > len(old_date) and entry['date'].startswith(old_date):
                    date_candidates[event_id].add(entry['date'])
        for event_id, dates in date_candidates.items():
            most_precise = max(dates, key=len)
            if all(most_precise.startswith(date) for date in dates):
                props = by_id[event_id]['properties']
                props['date'] = most_precise
                props['date_precision'] = 'day' if len(most_precise) == 10 else 'month' if len(most_precise) == 7 else 'year'
        consumed = {entry['entry_id'] for record in records for entry in record['properties'].get('source_entries', [])}
        for page in report['pages']:
            if page['status'] == 'unavailable':
                continue
            data = fetcher.fetch(page['title'])
            source = {'url': page['url'], 'title': page['title'].replace('_', ' '), 'kind': 'Wikipedia', 'revision': data['revision'], 'retrieved_at': data['retrieved_at']}
            # Only exact source identities are considered consumed.
            existing = [{'properties': {'source_entries': [{'entry_id': entry['entry_id']} for entry in report['entries'] if entry['source_title'] == page['title'] and entry['entry_id'] in consumed]}}]
            additional.extend(parse_unusual(data['html'], page['title'], source, existing))
        records = reconcile(records + additional)
        coverage = json.loads((ROOT / 'web/data/coverage.json').read_text())
        for page in report['pages']:
            if page['status'] != 'unavailable':
                coverage.setdefault('sources', {}).setdefault(page['title'], {}).update(status='parsed' if page.get('entries') else 'index', revision=page['revision'], retrieved_at=page['retrieved_at'], family='aviation lists')
        coverage['audit_repair'] = {'generated_at': STAMP(), 'extracted_source_entries': len(additional), 'article_enrichment_required_for_new_entries': True}
        publish(records, coverage)
        # publish already reruns the audit against the repaired records.
        report = json.loads((ROOT / 'web/data/audit.json').read_text())
    write_report(report, ROOT / 'web/data')
    coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}
    coverage['source_entry_audit'] = report['summary']
    coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    main()
