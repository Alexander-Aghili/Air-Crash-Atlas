"""Enumerate source rows before extraction, retaining raw text and stable identities."""
import hashlib
import re
from html import escape
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup
from pipeline.articles import extract_date

YEAR = re.compile(r'\b(?:18|19|20)\d{2}\b')
ACTION = re.compile(r'crash|colli(?:sion|ded)|shot down|shootdown|ditch|overran|overshot|undershot|disappear|went missing|accident|hijack|explosion|engine failure|forced landing|destroyed|damaged|lost|killed', re.I)
EXCLUDED = re.compile(r'reflist|navbox|toc|metadata|hatnote|sidebar|infobox|reference', re.I)


def normalize(text):
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip()


def entry_identity(title, text):
    return hashlib.sha256((unquote(title).replace(' ', '_') + '\n' + normalize(text)).encode()).hexdigest()[:24]


def source_entry(source, text):
    title = unquote(urlparse(source['url']).path[6:])
    return {'entry_id': entry_identity(title, text), 'source_url': source['url'],
            'revision': source.get('revision'), 'text': normalize(text)}


def date_text(text, year=None):
    text = normalize(text)
    # A leading event date and its year heading outrank later recovery dates,
    # citation years, flight numbers, and other four-digit numbers in the prose.
    leading = re.match(r"^(?:On |In )?((?:\d{1,2}\s+[A-Z][a-z]+(?:\s+(?:18|19|20)\d{2})?|[A-Z][a-z]+\s+(?:18|19|20)\d{2}|[A-Z][a-z]+\s+\d{1,2}(?!\d)(?:,?\s+(?:18|19|20)\d{2})?|(?:18|19|20)\d{2}-\d{2}-\d{2}|(?:18|19|20)\d{2}))\b", text)
    if leading:
        text = leading[1]
    date = extract_date(BeautifulSoup('<span>' + escape(text) + '</span>', 'lxml').span)
    if date:
        return date
    if year and not YEAR.search(text):
        # Source prose can put punctuation or notes between the day/month and
        # the inherited heading year. Keep the original text separately.
        clean = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", text)
        partial = re.search(r"\b(?:\d{1,2}\s+[A-Z][a-z]+|[A-Z][a-z]+\s+\d{1,2})\b", clean)
        if partial:
            date = extract_date(BeautifulSoup('<span>' + escape(partial[0] + ' ' + year) + '</span>', 'lxml').span)
            if date:
                return date
    month = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:18|19|20)\d{2})\b', text + (' ' + year if year and not YEAR.search(text) else ''))
    if month:
        from datetime import datetime
        return datetime.strptime(month[0], '%B %Y').strftime('%Y-%m')
    found = YEAR.search(text)
    if found:
        return found[0]
    if year and re.search(r'January|February|March|April|May|June|July|August|September|October|November|December|Spring|Summer|Autumn|Fall|Winter', text, re.I):
        return year
    return None


def table_rows(table):
    """Expand both header and data rowspans; retain bottom-level column labels."""
    spans, headers = {}, []
    for row in table.find_all('tr'):
        if row.find_parent('table') is not table:
            continue
        raw = row.find_all(['td', 'th'], recursive=False)
        if not raw:
            continue
        cells, col = [], 0
        def inherited():
            nonlocal col
            cell, remaining = spans[col]
            cells.append(cell)
            if remaining == 1:
                del spans[col]
            else:
                spans[col] = (cell, remaining - 1)
            col += 1
        for cell in raw:
            while col in spans:
                inherited()
            width = int(cell.get('colspan', 1))
            height = int(cell.get('rowspan', 1))
            for _ in range(width):
                cells.append(cell)
                if height > 1:
                    spans[col] = (cell, height - 1)
                col += 1
        while col in spans:
            inherited()
        # Some data rows use th cells for totals. A real heading row has no td.
        if all(c.name == 'th' for c in raw):
            labels = [normalize(c.get_text(' ', strip=True)).lower() for c in cells]
            if any(re.search(r'\bdate\b|^year$', label) for label in labels):
                headers = labels
            elif len(raw) == 1 and int(raw[0].get('colspan', 1)) > 1:
                headers = []
            continue
        yield row, dict(zip(headers, cells))


def enumerate_entries(html, title):
    """Inventory dated rows, definition entries, bullets, and narrative paragraphs.

    Unreadable dates and compound narratives stay visible as review candidates.
    This inventory never invokes the extraction parsers.
    """
    soup = BeautifulSoup(html, 'lxml')
    content = soup.select_one('.mw-parser-output') or soup
    year, section, pending = None, '', None
    entries, seen = [], set()
    table_values = {}
    for table in content.find_all('table'):
        if table.find_parent(class_=EXCLUDED) or EXCLUDED.search(' '.join(table.get('class', []))):
            continue
        for row, values in table_rows(table):
            table_values[id(row)] = values
    for node in content.find_all(['h2', 'h3', 'h4', 'dt', 'dd', 'li', 'p', 'tr']):
        text = normalize(node.get_text(' ', strip=True))
        if node.name.startswith('h'):
            heading = text.replace('[ edit ]', '').replace('[edit]', '').strip()
            section = node.get('id') or (node.find(id=True).get('id') if node.find(id=True) else '')
            found = re.search(r'\b((?:18|19|20)\d{2})(?:s)?\b', heading)
            year = found[1] if found else year
            pending = None
            continue
        if node.find_parent(class_=EXCLUDED):
            continue
        if node.name == 'dt':
            pending = text
            continue
        if len(text) < 15:
            continue
        values, raw_date, date, reason = {}, '', None, None
        if node.name == 'tr':
            if id(node) not in table_values:
                continue
            values = table_values[id(node)]
            date_node = next((value for key, value in values.items() if re.search(r'\bdate\b|^year$', key)), None)
            if date_node is None:
                # No date header: audit event-looking rows rather than silently losing them.
                if not (ACTION.search(text) and YEAR.search(text)):
                    continue
                if node.find('table'):
                    # Wrapper rows around aggregate tables are not individual losses.
                    continue
                possible_dates = []
                for cell in node.find_all(['td', 'th'], recursive=False):
                    cell_text = normalize(cell.get_text(' ', strip=True))
                    if re.fullmatch(r"(?:\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})(?:\s*\[[^\]]*\])*", cell_text):
                        if date_text(cell_text):
                            possible_dates.append(cell)
                if len(possible_dates) == 1:
                    date_node = possible_dates[0]
                    raw_date = date_node.get_text(' ', strip=True)
                    date = date_text(raw_date)
                    values = {'date (inferred column)': date_node}
                else:
                    raw_date = text
                    reason = 'table_date_column_unrecognized' 
            else:
                clone = BeautifulSoup(str(date_node), 'lxml')
                for ref in clone.select('sup'):
                    ref.decompose()
                raw_date = clone.get_text(' ', strip=True)
                date = date_text(raw_date, year)
                if not date:
                    reason = 'date_unresolved'
        elif node.name == 'dd':
            if node.find_parent('table') or not pending:
                continue
            raw_date = pending
            date = date_text(raw_date, year)
            if re.search(r'\bor\b|sources cite|\d\s*[/–]\s*\d', raw_date, re.I):
                reason = 'ambiguous_source_date'
            elif not date:
                reason = 'date_unresolved'
        elif node.name in ['li', 'p']:
            if node.find_parent(['table', 'dd', 'li']) and node.name == 'p':
                continue
            if node.find_parent(['table', 'dd']) or (node.name == 'li' and node.find(['ul', 'ol'])):
                continue
            dated_prefix = re.match(r"^(?:On |In )?(?:\d{1,2} [A-Z][a-z]+|[A-Z][a-z]+ \d{1,2}|(?:18|19|20)\d{2})\b", text)
            if not ACTION.search(text) and not dated_prefix:
                continue
            raw_date = text
            date = date_text(text, year)
            if not date:
                if not YEAR.search(text):
                    continue
                reason = 'date_unresolved'
            # A paragraph describing several losses is not one event.
            dates = re.findall(r'\b\d{1,2}\s+[A-Z][a-z]+\s+(?:18|19|20)\d{2}\b|\b[A-Z][a-z]+\s+\d{1,2},?\s+(?:18|19|20)\d{2}\b', text)
            if len(set(dates)) > 1:
                reason = 'multiple_event_dates_in_one_entry'
        else:
            continue
        entry_id = entry_identity(title, text)
        if entry_id in seen:
            reason = reason or 'duplicate_source_text_requires_context_review'
        seen.add(entry_id)
        links = list(dict.fromkeys(unquote(a['href'][6:]).split('#')[0] for a in node.select('a[href^="/wiki/"]') if ':' not in unquote(a['href'][6:]).split('#')[0] and not a['href'].startswith('/wiki/List_')))
        entries.append({'entry_id': entry_id, 'source_position': len(entries) + 1, 'text': text, 'layout': node.name,
                        'date': date, 'raw_date': raw_date, 'section': section,
                        'links': links, 'review_reason': reason,
                        'fields': {key: normalize(value.get_text(' ', strip=True)) for key, value in values.items()},
                        '_node': node, '_soup': soup})
    return entries


def parse_unusual(html, title, source, existing):
    from pipeline.extract import event, URL, references
    from pipeline.lists import MILITARY
    consumed = {entry['entry_id'] for row in existing for entry in row['properties'].get('source_entries', [])}
    records = []
    for entry in enumerate_entries(html, title):
        if entry['entry_id'] in consumed or not entry['date'] or entry['review_reason']:
            continue
        # Match only event article links, never arbitrary airports or manufacturers.
        links = [link for link in entry['links'] if re.search(r'crash|collision|disaster|shootdown|accident|Flight_\d', link, re.I)]
        fields = entry['fields']
        serials = list(dict.fromkeys(re.findall(r'\b\d{2}-\d{4,6}\b|\b[A-Z]{1,2}-[A-Z0-9]{3,6}\b|\bN\d{1,5}[A-Z]{0,2}\b', entry['text'])))
        variant = next((fields[key] for key in ['aircraft type', 'aircraft', 'variant', 'type'] if key in fields), '')
        registration = next((fields[key] for key in ['registration', 'serial', 'serial number', 'id'] if key in fields), '')
        aircraft = [{'type': variant, 'registration': registration, 'operator': fields.get('operator', '')}] if variant or registration else [{'type': '', 'registration': serial, 'operator': ''} for serial in serials]
        # Operator and source context outweigh mentions of a military airport or rescuer.
        category = 'military' if MILITARY.search(title) or re.search(r'\b(?:USAF|RAF|USMC)|(?:army|navy|military|air force)\s+(?:aircraft|plane|helicopter|flight)', entry['text'], re.I) else 'civil'
        name = links[0].replace('_', ' ') if links else entry['date'] + ' · ' + (' / '.join(serials) or entry['text'][:85])
        linked_source = dict(source, url=URL(title) + ('#' + entry['section'] if entry['section'] else ''))
        record = event(name, entry['date'], entry['text'], linked_source, entry['text'][:180], category, aircraft)
        record['properties'].update(article_titles=links[:1], related_article_titles=links[1:], date_original=entry['raw_date'], location_text=fields.get('location', fields.get('site', entry['text'])), raw_list_fields=fields)
        record['properties']['sources'].extend(references(entry['_node'], entry['_soup']))
        records.append(record)
    return records
