"""Event-article extraction. Geographic context never supplies crash coordinates."""

import re
from datetime import datetime
from urllib.parse import unquote, urljoin
from bs4 import BeautifulSoup

SEPTEMBER_11_FLIGHTS = {
    "American Airlines Flight 11",
    "American Airlines Flight 77",
    "United Airlines Flight 175",
    "United Airlines Flight 93",
}

COUNTRIES = [
    "United States",
    "United Kingdom",
    "France",
    "Spain",
    "Japan",
    "Canada",
    "Australia",
    "India",
    "Indonesia",
    "Brazil",
    "Russia",
    "China",
    "Germany",
    "Italy",
    "Mexico",
    "South Korea",
    "Taiwan",
    "Nepal",
    "Pakistan",
    "Colombia",
    "Peru",
    "Argentina",
    "Thailand",
    "Malaysia",
    "Philippines",
    "New Zealand",
    "Vietnam",
    "Turkey",
    "Iran",
    "Saudi Arabia",
    "Egypt",
    "Nigeria",
    "South Africa",
]


def extract_date(node):
    if not node:
        return None
    text = node.get_text(" ", strip=True).replace("\xa0", " ")
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        try:
            return datetime.strptime(iso[1], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    for pattern, fmt in [
        (r"\b(\d{1,2} [A-Z][a-z]+ \d{4})", "%d %B %Y"),
        (r"\b([A-Z][a-z]+ \d{1,2},? \d{4})", "%B %d %Y"),
    ]:
        found = re.search(pattern, text)
        if found:
            try:
                return datetime.strptime(found[1].replace(",", ""), fmt).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    return None


def coordinates(node):
    result = []
    for geo in node.select(".geo"):
        try:
            lat, lon = [float(x.strip()) for x in geo.get_text().split(";")]
            if abs(lat) <= 90 and abs(lon) <= 180:
                point = {"type": "Point", "coordinates": [lon, lat]}
                if point not in result:
                    result.append(point)
        except ValueError:
            continue
    return result


def extract_images(soup, box, source):
    images = []
    candidates = list(box.select("a[href]")) if box else []
    candidates += list(soup.select("figure a[href], .thumb a[href]"))
    for a in candidates:
        href = a.get("href", "")
        img = a.find("img")
        if not img or not re.search(r"/wiki/File:", href):
            continue
        try:
            if int(img.get("width", 0)) < 140 or int(img.get("height", 0)) < 60:
                continue
        except ValueError:
            continue
        src = img.get("src", "")
        url = urljoin("https://en.wikipedia.org", href)
        if not src.startswith(
            (
                "//upload.wikimedia.org/",
                "//thumb.wikimedia.org/",
                "https://upload.wikimedia.org/",
                "https://thumb.wikimedia.org/",
            )
        ):
            continue
        container = (
            a.find_parent("figure")
            or a.find_parent(class_="thumb")
            or a.find_parent("td")
        )
        caption_node = (
            container.select_one("figcaption,.thumbcaption,.infobox-caption")
            if container
            else None
        )
        caption = (
            caption_node.get_text(" ", strip=True)
            if caption_node
            else img.get("alt", "")
        )
        if not caption:
            caption = unquote(href.split("File:", 1)[1]).replace("_", " ")
        image = {
            "url": url,
            "thumbnail": urljoin("https://en.wikipedia.org", src),
            "caption": caption,
            "kind": "article illustration",
            "source_url": source["url"],
            "revision": source.get("revision"),
        }
        if not any(old["url"] == url for old in images):
            images.append(image)
        if len(images) >= 6:
            break
    return images


def article(html, title, source, fallback_date=None):
    from pipeline.extract import event

    soup = BeautifulSoup(html, "lxml")
    boxes = soup.select(".infobox")
    box = next(
        (
            b
            for b in boxes
            if any(
                re.match(r"(?i)^(date|site)$", h.get_text(" ", strip=True))
                for h in b.select("th,.infobox-label")
            )
        ),
        None,
    )
    fields = {}
    aircraft = []
    aircraft_context = False
    if box:
        for row in box.select("tr"):
            header = row.find(class_="infobox-header")
            if header and re.search(
                r"aircraft", header.get_text(" ", strip=True), re.I
            ):
                aircraft_context = True
            h = row.find(class_="infobox-label") or row.find("th")
            td = row.find(class_="infobox-data") or row.find("td")
            if not h or not td:
                continue
            key = h.get_text(" ", strip=True).lower().replace("\xa0", " ")
            fields.setdefault(key, td)
            value = td.get_text(" ", strip=True)
            if key in ["aircraft type", "aircraft"] or (
                key == "type" and aircraft_context
            ):
                aircraft.append({"type": value, "registration": "", "operator": ""})
            elif aircraft and key in ["registration", "operator"]:
                aircraft[-1][key] = value
    date = extract_date(fields.get("date")) or fallback_date
    if title.replace("_", " ") == "Fairfax, California B-17 crash":
        date = "1946-05-16"
    if not date:
        return None
    summary = fields.get("summary")
    summary_text = summary.get_text(" ", strip=True) if summary else ""
    body = soup.select_one(".mw-parser-output") or soup
    lead = next(
        (
            p.get_text(" ", strip=True)
            for p in body.find_all("p", recursive=False)
            if len(p.get_text(" ", strip=True)) > 60
        ),
        "",
    )
    category = (
        "military"
        if re.search(
            r"air force|navy|army|military|\bRAF\b|\bUSAF\b",
            " ".join(n.get_text(" ", strip=True) for n in fields.values())
            + " "
            + " ".join(a.get("operator", "") for a in aircraft),
            re.I,
        )
        else "civil"
    )
    r = event(
        title.replace("_", " "),
        date,
        " ".join([summary_text, lead]).strip(),
        source,
        category=category,
        aircraft=aircraft,
    )
    p = r["properties"]
    p["description"] = summary_text or lead
    impact_text = title.replace("_", " ") + " " + summary_text
    impact = re.search(
        r"crash|colli(?:sion|ded)|ditching|overr(?:an|un)|hard landing|undershot|overshot|runway excursion|controlled flight into|break.?up|(?:mid[ -]air|in[ -]flight) disintegration|shot down|shootdown",
        impact_text,
        re.I,
    )
    near_miss = re.search(
        r"near[ -](?:crash|miss|collision)|narrowly (?:avoided|missed)",
        impact_text,
        re.I,
    )
    non_impact = re.search(
        r"hijack|turbulence|fuel dumping|decompression|door plug|uncontained engine failure|loss of cabin pressure",
        summary_text,
        re.I,
    )
    if near_miss or (non_impact and not impact):
        p["event_type"] = "incident"
    elif impact and p["event_type"] == "incident":
        p["event_type"] = "crash"
    fatalities_text = (
        fields.get("fatalities").get_text(" ", strip=True)
        if fields.get("fatalities")
        else ""
    )
    if (
        not impact
        and re.match(r"^0(?:\D|$)", fatalities_text)
        and re.search(
            r"engine failure|fuel exhaustion|hydraulic failure", summary_text, re.I
        )
        and not re.search(r"crashed|crash-landed|ditched|collided|overran", lead, re.I)
    ):
        p["event_type"] = "incident"
    if date == "2001-09-11" and title.replace("_", " ") in SEPTEMBER_11_FLIGHTS:
        p["event_type"] = "crash"
        p["search_aliases"] = [
            "9/11",
            "9-11",
            "911",
            "September 11",
            "September 11 attacks",
            (
                "World Trade Center"
                if "Flight 11" in title.replace("_", " ")
                or "Flight 175" in title.replace("_", " ")
                else (
                    "Pentagon"
                    if "Flight 77" in title.replace("_", " ")
                    else "Shanksville"
                )
            ),
        ]
    p["images"] = extract_images(soup, box, source)
    p["article_titles"] = [title]
    p["article_url"] = source["url"]
    p["date_precision"] = "day" if len(date) == 10 else "year"
    for name in ["fatalities", "occupants", "survivors"]:
        field = fields.get("total " + name) or fields.get(name)
        if field:
            p[name] = field.get_text(" ", strip=True)
    site = fields.get("site")
    if site:
        # Clone before removing annotations and coordinates from display text.
        clean = BeautifulSoup(str(site), "lxml")
        for node in clean.select(
            "sup,style,.coordinates,.geo-inline,.geo,.geo-dms,.geo-dec,.geo-nondefault,.latitude,.longitude"
        ):
            node.decompose()
        p["location_text"] = clean.get_text(" ", strip=True)
        for country in sorted(COUNTRIES, key=len, reverse=True):
            if re.search(r"\b" + re.escape(country) + r"\b", p["location_text"], re.I):
                p["state"] = country
                break
        if p["state"] == "Unknown" and re.search(
            r"\b(?:U\.?S\.?A?\.?|United States of America)\b", p["location_text"]
        ):
            p["state"] = "United States"
        pts = coordinates(site)
        invalid = re.search(
            r"last (known|contact|position)|disappear|presumed|^memorial|wreckage display",
            p["location_text"],
            re.I,
        )
        if (
            pts
            and not invalid
            and p["event_type"] not in ["disappearance", "incident", "ground incident"]
        ):
            r["geometry"] = pts[0]
            p["site_geometries"] = pts
            p.update(
                location_kind="impact site",
                location_quality="source supplied",
                evidence={
                    "method": "Event-specific coordinates in the accident infobox Site field. No airport, town, memorial, or general article coordinates substituted.",
                    "source_url": source["url"],
                    "revision": source.get("revision"),
                    "retrieved_at": source.get("retrieved_at"),
                },
            )
        elif invalid:
            p["evidence"][
                "method"
            ] = "Source describes a last-known, presumed, or related location; actual impact coordinates remain unresolved."
    if "collision" in (summary_text + title).lower() and p["event_type"] != "incident":
        p["event_type"] = "collision"
    if re.search(r"disappear|went missing", summary_text, re.I):
        p["event_type"] = "disappearance"
        r["geometry"] = None
        p.update(location_kind="unknown", location_quality="missing")
    return r
