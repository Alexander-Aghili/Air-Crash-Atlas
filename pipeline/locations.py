"""Resolve explicitly sourced wreck-site references during the normal update.

A reviewed source reference identifies a source entity, not hard-coded coordinates.
Community-mapped wreck locations remain approximate and cannot replace an already
established location. Dates, Wikipedia identity, and registrations must all match.
"""
import json
import re
from urllib.parse import unquote, urlparse
import requests
from pipeline.extract import ROOT, STAMP


def wikipedia_title(url):
    parsed = urlparse(url)
    if parsed.hostname != 'en.wikipedia.org' or not parsed.path.startswith('/wiki/'):
        return None
    return unquote(parsed.path[6:]).replace('_', ' ')


def matching_wreck(node, record, reference):
    p = record['properties']
    tags = node.get('tags', {})
    refs = {re.sub(r'\[.*?\]', '', a.get('registration', '')).strip() for a in p.get('aircraft', [])}
    titles = {wikipedia_title(p.get('article_url', '')), wikipedia_title(p.get('source_url', ''))}
    wiki = tags.get('wikipedia', '')
    return (
        node.get('type') == 'node'
        and node.get('id') == reference['node_id']
        and tags.get('historic') == 'aircraft_wreck'
        and wiki.startswith('en:')
        and wiki[3:].replace('_', ' ') in titles
        and tags.get('start_date') == p['date']
        and tags.get('ref') == reference['registration']
        and reference['registration'] in refs
        and isinstance(node.get('lat'), (int, float))
        and isinstance(node.get('lon'), (int, float))
        and -90 <= node['lat'] <= 90 and -180 <= node['lon'] <= 180
    )


def supplement_locations(records, report, offline=False):
    cache = ROOT / 'cache'
    cache.mkdir(exist_ok=True)
    updates = []
    for record in records:
        p = record['properties']
        references = p.get('location_sources', [])
        if not references or record['geometry'] or p['event_type'] not in ('crash', 'collision', 'combat loss'):
            continue
        points, sources, names = [], [], []
        for reference in references:
            if reference.get('provider') != 'OpenStreetMap':
                continue
            node_id = reference['node_id']
            path = cache / f'osm-node-{node_id}.json'
            source_url = f'https://www.openstreetmap.org/node/{node_id}'
            try:
                if offline:
                    if not path.exists():
                        raise RuntimeError('Wreck-site source is not cached')
                    data = json.loads(path.read_text())
                else:
                    response = requests.get(
                        f'https://www.openstreetmap.org/api/0.6/node/{node_id}.json',
                        headers={'User-Agent': 'AviationCrashAtlas/0.3 (https://github.com/alexsky2)'},
                        timeout=20,
                    )
                    response.raise_for_status()
                    data = response.json()
                    path.write_text(json.dumps(data))
                node = next((n for n in data.get('elements', []) if matching_wreck(n, record, reference)), None)
                if node is None:
                    raise ValueError('Wreck-site identity, date, registration, or coordinates do not match')
                points.append({'type': 'Point', 'coordinates': [node['lon'], node['lat']]})
                names.append(node['tags']['name'])
                sources.append({'url': source_url, 'title': node['tags']['name'], 'kind': 'OpenStreetMap wreck site', 'revision': node.get('version'), 'retrieved_at': STAMP(), 'license': 'ODbL-1.0'})
                report.setdefault('location_sources', {})[source_url] = {'status': 'matched', 'revision': node.get('version')}
            except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
                report.setdefault('location_sources', {})[source_url] = {'status': 'failed', 'error': str(exc)}
        # Do not silently map only one aircraft when multiple sites are expected.
        if points and len(points) == len(references):
            record['geometry'] = points[0]
            p.update(
                site_geometries=points,
                location_kind='impact site', location_quality='approximate',
                location_text=' / '.join(names),
                uncertainty={'description': 'Approximate locations; accuracy has not been independently verified.'},
                evidence={'method': 'OpenStreetMap identifies these aircraft wreck sites.', 'source_url': sources[0]['url']},
            )
            p.setdefault('sources', []).extend(s for s in sources if not any(old['url'] == s['url'] for old in p['sources']))
            updates.append(p['event_id'])
    report['resolved_wreck_site_records'] = len(updates)
    return updates
