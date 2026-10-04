import json, math
from pathlib import Path
from urllib.parse import urlparse


def validate(records):
    ids = set()
    for f in records:
        assert f["id"] not in ids, "Duplicate event ID"
        ids.add(f["id"])
        p = f["properties"]
        assert p["date"] and p["sources"]
        for s in p["sources"]:
            u = urlparse(s["url"])
            assert (
                u.scheme in ["https", "http"]
                and u.hostname
                and not u.username
                and not u.password
            )
        if f["geometry"]:
            if p["event_type"] in ["incident", "ground incident", "accident"]:
                assert p["location_kind"] == "event site", "Non-impact event must not claim an impact site"
            assert f["geometry"]["type"] == "Point"
            lon, lat = f["geometry"]["coordinates"]
            assert (
                math.isfinite(lon)
                and math.isfinite(lat)
                and abs(lon) <= 180
                and abs(lat) <= 90
            )
            assert p["location_kind"] in [
                "impact site",
                "event site",
                "approximate area",
                "last-known position",
            ]
            assert p["location_quality"] != "missing"
            assert p["evidence"]["method"]
        else:
            assert p["location_quality"] == "missing"


if __name__ == "__main__":
    data = json.loads(
        (Path(__file__).resolve().parents[1] / "web/data/events.geojson").read_text()
    )
    validate(data["features"])
    print("Dataset valid")
