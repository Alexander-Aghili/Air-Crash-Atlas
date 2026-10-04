"""Parse dated bullets and event tables without treating aircraft totals as crashes."""

import re
from datetime import datetime
from urllib.parse import unquote, quote
from bs4 import BeautifulSoup
from pipeline.articles import extract_date

MILITARY = re.compile(
    r"military|air_force|airforce|Royal_Air_Force|RAF|F-15|Harrier|Lightning|Soviet|war|Chechen",
    re.I,
)


def parse_flexible(html, title, source):
    from pipeline.extract import event, URL, references

    if re.search(
        r"balloon|airship|spaceflight|accidents_and_disasters_by_death_toll",
        title,
        re.I,
    ):
        return []

    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".mw-parser-output") or soup
    records = []
    year = None
    section = ""

    def add(node, date, headers=None, cells=None):
        text = node.get_text(" ", strip=True)
        if len(text) < 35:
            return
        links = [
            unquote(a["href"][6:]).split("#")[0]
            for a in node.select('a[href^="/wiki/"]')
            if ":" not in unquote(a["href"][6:]).split("#")[0]
            and re.search(
                r"crash|disaster|collision|shootdown|accident|Flight_\d",
                a["href"],
                re.I,
            )
            and not re.match(
                r"/wiki/(?:List_|File:|Image:|Category:|Template:)", a["href"]
            )
        ]
        serials = list(
            dict.fromkeys(re.findall(r"\b\d{2}-\d{4,6}\b|\b[A-Z]{2}\d{3}\b", text))
        )
        aircraft = []
        if headers and cells:
            values = dict(zip(headers, cells))
            variant = next(
                (
                    values[k].get_text(" ", strip=True)
                    for k in ["aircraft", "aircraft type", "type", "variant"]
                    if k in values
                ),
                "",
            )
            registration = next(
                (
                    values[k].get_text(" ", strip=True)
                    for k in ["serial", "serial number", "registration", "id"]
                    if k in values
                ),
                "",
            )
            operator = (
                values["operator"].get_text(" ", strip=True)
                if "operator" in values
                else ""
            )
            if variant or registration:
                aircraft = [
                    {
                        "type": variant,
                        "registration": registration,
                        "operator": operator,
                    }
                ]
        if not aircraft:
            aircraft = [
                {"type": "", "registration": serial, "operator": ""}
                for serial in serials
            ]
        category = (
            "military"
            if MILITARY.search(title)
            or re.search(r"\b(?:USAF|RAF|USMC|Navy|Army)|air force", text, re.I)
            else "civil"
        )
        link = dict(
            source, url=URL(title) + (("#" + quote(section)) if section else "")
        )
        name = (
            links[0].replace("_", " ")
            if links
            else f"{date} · " + (" / ".join(serials) if serials else text[:85])
        )
        row = event(
            name, date, text, link, text[:180], category=category, aircraft=aircraft
        )
        row["properties"].update(
            article_titles=links[:1], related_article_titles=links[1:], location_text=text, location_evidence_pending=True
        )
        row["properties"]["sources"].extend(references(node, soup))
        records.append(row)

    for node in content.find_all(["h2", "h3", "h4", "h5", "h6", "dt", "li", "table"]):
        if node.name == "dt" and re.fullmatch(r"(?:18|19|20)\d{2}", node.get_text(" ", strip=True)):
            year = node.get_text(" ", strip=True)
        elif node.name.startswith("h"):
            heading = node.get_text(" ", strip=True)
            m = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", heading)
            if m:
                year = m[1]
            section = node.get("id") or (
                node.find(id=True).get("id") if node.find(id=True) else ""
            )
        elif node.name == "li":
            if node.find_parent(["li", "table", "dd"]) or node.find_parent(
                class_=re.compile(r"reflist|navbox|toc|redirect|metadata")
            ):
                continue
            text = node.get_text(" ", strip=True)
            prefix = text[:65]
            date = extract_date(BeautifulSoup(prefix, "lxml"))
            if not re.match(
                r"^(?:\d{1,2}\s+[A-Z][a-z]+|[A-Z][a-z]+\s+\d{1,2}|(?:18|19|20)\d{2})\b",
                prefix,
            ):
                continue
            if not date and year:
                for pattern, fmt in [
                    (r"^(\d{1,2} [A-Z][a-z]+)", "%d %B %Y"),
                    (r"^([A-Z][a-z]+ \d{1,2})", "%B %d %Y"),
                ]:
                    m = re.match(pattern, prefix)
                    if m:
                        try:
                            date = datetime.strptime(m[1] + " " + year, fmt).strftime(
                                "%Y-%m-%d"
                            )
                        except ValueError:
                            pass
            if date:
                add(node, date)
        elif node.name == "table" and "wikitable" in node.get("class", []):
            headers = []
            spans = {}
            for tr in node.find_all("tr", recursive=False) or node.select(
                ":scope > tbody > tr"
            ):
                raw = tr.find_all(["th", "td"], recursive=False)
                if not raw:
                    continue
                if all(c.name == "th" for c in raw):
                    candidate = [c.get_text(" ", strip=True).lower() for c in raw]
                    if any(k in ["date", "year"] for k in candidate):
                        headers = candidate
                        spans = {}
                    continue
                if not headers:
                    continue
                cells = []
                col = 0
                for c in raw:
                    while col in spans:
                        old, remaining = spans[col]
                        cells.append(old)
                        if remaining <= 1:
                            del spans[col]
                        else:
                            spans[col] = (old, remaining - 1)
                        col += 1
                    span = int(c.get("colspan", 1))
                    rows = int(c.get("rowspan", 1))
                    for _ in range(span):
                        cells.append(c)
                        if rows > 1:
                            spans[col] = (c, rows - 1)
                        col += 1
                while col in spans:
                    old, remaining = spans[col]
                    cells.append(old)
                    if remaining <= 1:
                        del spans[col]
                    else:
                        spans[col] = (old, remaining - 1)
                    col += 1
                values = dict(zip(headers, cells))
                date_node = values.get("date") or values.get("year")
                date = extract_date(date_node)
                if not date and date_node:
                    m = re.fullmatch(
                        r"(18\d{2}|19\d{2}|20\d{2})",
                        date_node.get_text(" ", strip=True),
                    )
                    if m:
                        date = m[1]
                if date:
                    add(tr, date, headers, cells)
    return records
