import unittest
from pipeline.extract import parse_list, event, article, reconcile
from pipeline.validate import validate

SOURCE = {
    "url": "https://en.wikipedia.org/wiki/Test",
    "revision": 1,
    "retrieved_at": "2026-10-02",
}


class PipelineTests(unittest.TestCase):
    def test_collision_total_fatalities_survive_merge_with_old_publication(self):
        html = '<table class="infobox"><tr><th>Date</th><td>30 June 1956</td></tr><tr><th>Summary</th><td>Mid-air collision</td></tr><tr><th>Total fatalities</th><td>128</td></tr><tr><th>Fatalities</th><td>70</td></tr><tr><th>Fatalities</th><td>58</td></tr><tr><th>Total survivors</th><td>0</td></tr></table>'
        current = article(html, "1956 Grand Canyon mid-air collision", SOURCE)
        old = event("1956 Grand Canyon mid-air collision", "1956-06-30", "", SOURCE)
        old["properties"]["fatalities"] = "70"
        self.assertEqual(current["properties"]["fatalities"], "128")
        self.assertEqual(reconcile([current, old])[0]["properties"]["fatalities"], "128")

    def test_wreck_sources_require_matching_event_date_registration_and_all_sites(self):
        import json, tempfile, copy
        from pathlib import Path
        from unittest.mock import patch
        from pipeline.locations import matching_wreck, supplement_locations
        record = event("Collision", "1956-06-30", "Mid-air collision", SOURCE, aircraft=[{"registration":"N1"},{"registration":"N2"}])
        record["properties"]["event_type"] = "collision"
        references = [{"provider":"OpenStreetMap","node_id":1,"registration":"N1"},{"provider":"OpenStreetMap","node_id":2,"registration":"N2"}]
        record["properties"]["location_sources"] = references
        node = {"type":"node","id":1,"lat":36.18,"lon":-111.82,"tags":{"historic":"aircraft_wreck","wikipedia":"en:Test","start_date":"1956-06-30","ref":"N1","name":"Wreck 1"}}
        self.assertTrue(matching_wreck(node, record, references[0]))
        for key, value in [("historic","memorial"),("wikipedia","en:Other"),("start_date","1957-06-30"),("ref","N3")]:
            bad = copy.deepcopy(node); bad["tags"][key] = value
            self.assertFalse(matching_wreck(bad, record, references[0]))
        with tempfile.TemporaryDirectory() as directory, patch('pipeline.locations.ROOT', Path(directory)):
            cache = Path(directory)/'cache';cache.mkdir()
            (cache/'osm-node-1.json').write_text(json.dumps({"elements":[node]}))
            self.assertEqual(supplement_locations([record],{},offline=True),[])
            self.assertIsNone(record["geometry"])
            other=copy.deepcopy(node);other.update(id=2,lat=36.19);other["tags"].update(ref="N2",name="Wreck 2")
            (cache/'osm-node-2.json').write_text(json.dumps({"elements":[other]}))
            self.assertEqual(supplement_locations([record],{},offline=True),[record["id"]])
            self.assertEqual(len(record["properties"]["site_geometries"]),2)
            self.assertEqual(record["properties"]["location_quality"],"approximate")
            validate([record])

    def test_dates_multiple_entries_and_verified_section(self):
        html = '<div class="mw-parser-output"><h2 id="January–March_1946">January–March 1946</h2><dl><dt>16 May</dt><dd>B-17 44-85510 crashed near Fairfax; historical account awaiting coordinate review.</dd><dd>Another aircraft 44-85511 crashed offshore in a different event on the same day.</dd></dl></div>'
        rows = parse_list(html, "Test", SOURCE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["properties"]["date"], "1946-05-16")
        self.assertIn("#January", rows[0]["properties"]["source_url"])
        self.assertIsNone(rows[0]["geometry"])
        self.assertEqual(
            rows[0]["properties"]["aircraft"][0]["registration"], "44-85510"
        )
        validate(rows)

    def test_no_airport_or_memorial_substitution(self):
        html = '<table class="infobox"><tr><th>Date</th><td><span class="bday">2000-01-01</span></td></tr><tr><th>Site</th><td>Offshore</td></tr><tr><th>Origin</th><td><span class="geo">40; -80</span></td></tr></table>'
        self.assertIsNone(article(html, "Test", SOURCE)["geometry"])

    def test_fairfax_merge(self):
        a = event(
            "Fairfax, California B-17 crash",
            "1946-05-16",
            "",
            SOURCE,
            aircraft=[{"registration": "44-85510"}],
        )
        b = event(
            "16 May 1946 B-17",
            "1946-05-16",
            "Historical description",
            dict(SOURCE, url=SOURCE["url"] + "#1946"),
            aircraft=[{"registration": "44-85510"}],
        )
        merged = reconcile([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["properties"]["sources"]), 2)
        self.assertIsNone(merged[0]["geometry"])

    def test_bounds_and_geometry_quality(self):
        r = event("Test", "2000", "", SOURCE)
        r["geometry"] = {"type": "Point", "coordinates": [200, 0]}
        with self.assertRaises(AssertionError):
            validate([r])


if __name__ == "__main__":
    unittest.main()


class MediaTests(unittest.TestCase):
    def test_episode_requires_subject_link(self):
        from pipeline.extract import match_episodes, URL

        r = event(
            "USAir Flight 427", "1994-09-08", "", {"url": URL("USAir_Flight_427")}
        )
        data = {
            "revision": 1,
            "retrieved_at": "2026-10-02",
            "html": '<h2 id="Season_4">Season 4</h2><table><tr><td>30</td><td>5</td><td>"Hidden Danger"</td><td><a href="/wiki/USAir_Flight_427">USAir Flight 427</a></td></tr></table>',
        }
        self.assertEqual(match_episodes([r], data), 1)
        self.assertEqual(r["properties"]["media"][0]["title"], "Hidden Danger")


class CivilTests(unittest.TestCase):
    def test_year_heading_is_not_a_country(self):
        from pipeline.extract import parse_civil

        html = '<div class="mw-parser-output"><h2 id="1994">1994</h2><ul><li>On 8 September 1994, <a href="/wiki/USAir_Flight_427">USAir Flight 427</a> crashed in Pennsylvania during approach.</li></ul></div>'
        row = parse_civil(
            html,
            "List_of_accidents_and_incidents_involving_commercial_aircraft",
            SOURCE,
        )[0]
        self.assertEqual(row["properties"]["state"], "Unknown")
        self.assertEqual(row["properties"]["date"], "1994-09-08")


class InheritanceTests(unittest.TestCase):
    def test_flight_number_cannot_be_a_year(self):
        from pipeline.extract import parse_civil

        html = '<h2 id="2000">2000</h2><ul><li>December 29 – <a href="/wiki/British_Airways_Flight_2069">British Airways Flight 2069</a> experienced an attempted hijacking. No injuries.</li></ul>'
        row = parse_civil(
            html,
            "List_of_accidents_and_incidents_involving_commercial_aircraft",
            SOURCE,
        )[0]
        self.assertEqual(row["properties"]["date"], "2000-12-29")
        self.assertEqual(row["properties"]["event_type"], "incident")


class DiscoveryTests(unittest.TestCase):
    def test_image_links_are_not_accident_articles(self):
        from pipeline.extract import parse_civil

        html = '<h3 id="Algeria">Algeria</h3><ul><li>24 July 2014 <a href="/wiki/File:Crash_site.jpg">Crash image</a> shows <a href="/wiki/Air_Algérie_Flight_5017">Air Algérie Flight 5017</a> which crashed in Mali.</li></ul>'
        row = parse_civil(
            html,
            "List_of_accidents_and_incidents_involving_airliners_by_location",
            SOURCE,
        )[0]
        self.assertEqual(row["properties"]["name"], "Air Algérie Flight 5017")
        self.assertTrue(
            all(not t.startswith("File:") for t in row["properties"]["article_titles"])
        )


class ArticleEvidenceTests(unittest.TestCase):
    def test_site_coordinates_and_american_date(self):
        html = '<table class="infobox"><tr><th>Date</th><td>September 8, 1994</td></tr><tr><th>Site</th><td>Pennsylvania, United States <span class="geo">40.6; -80.3</span></td></tr><tr><th>Origin</th><td><span class="geo">0; 0</span></td></tr></table>'
        row = article(html, "USAir_Flight_427", SOURCE)
        self.assertEqual(row["geometry"]["coordinates"], [-80.3, 40.6])
        self.assertEqual(row["properties"]["date"], "1994-09-08")
        self.assertEqual(
            row["properties"]["location_text"], "Pennsylvania, United States"
        )

    def test_multiple_collision_sites_and_no_presumed_site(self):
        html = '<table class="infobox"><tr><th>Date</th><td>1956-06-30</td></tr><tr><th>Site</th><td>Crash sites <span class="geo">36; -112</span><span class="geo">36.1; -112.1</span></td></tr></table>'
        row = article(html, "Test_collision", SOURCE)
        self.assertEqual(len(row["properties"]["site_geometries"]), 2)
        self.assertIsNone(
            article(html.replace("Crash sites", "Presumed location"), "Test", SOURCE)[
                "geometry"
            ]
        )

    def test_country_word_boundaries_and_merge(self):
        html = '<table class="infobox"><tr><th>Date</th><td>2009-06-30</td></tr><tr><th>Site</th><td>Indian Ocean, near Comoros</td></tr></table>'
        self.assertEqual(
            article(html, "Test", SOURCE)["properties"]["state"], "Unknown"
        )
        a = event("Test", "2000", "", SOURCE)
        b = event("Test", "2000", "", SOURCE)
        b["properties"]["state"] = "United States"
        self.assertEqual(reconcile([a, b])[0]["properties"]["state"], "United States")

    def test_image_caption_and_credit_link(self):
        html = '<table class="infobox"><tr><th>Date</th><td>2000-01-01</td></tr></table><figure><a href="/wiki/File:Aircraft.jpg"><img width="300" height="200" src="//upload.wikimedia.org/example.jpg"></a><figcaption>Aircraft before the accident</figcaption></figure>'
        image = article(html, "Test", SOURCE)["properties"]["images"][0]
        self.assertEqual(image["caption"], "Aircraft before the accident")
        self.assertEqual(
            image["url"], "https://en.wikipedia.org/wiki/File:Aircraft.jpg"
        )


class RedirectTests(unittest.TestCase):
    def test_cached_redirect_resolves_article(self):
        import tempfile, hashlib, json
        from pathlib import Path
        from pipeline.enrich import Wikimedia

        with tempfile.TemporaryDirectory() as temporary:
            client = Wikimedia(offline=True)
            client.cache = Path(temporary)
            for title, html in [
                (
                    "Alias",
                    '<ul class="redirectText"><li><a href="/wiki/Actual">Actual</a></li></ul>',
                ),
                ("Actual", '<table class="infobox">Actual accident</table>'),
            ]:
                path = client.cache / (
                    hashlib.sha256(title.encode()).hexdigest() + ".json"
                )
                path.write_text(
                    json.dumps(
                        {"html": html, "revision": 1, "retrieved_at": "2026-10-02"}
                    )
                )
            result = client.fetch("Alias")
            self.assertEqual(result["canonical_title"], "Actual")
            self.assertIn("Actual accident", result["html"])


class NonImpactTests(unittest.TestCase):
    def test_decompression_with_aircraft_disintegration_is_mapped_crash(self):
        for summary, expected in [
            ("Explosive decompression and mid-air disintegration", "crash"),
            ("Explosive decompression and in-flight disintegration", "crash"),
            ("Explosive decompression; aircraft landed safely", "incident"),
            ("Decompression following uncontained engine failure and turbine disk disintegration", "incident"),
        ]:
            html = f'<table class="infobox"><tr><th>Date</th><td>1954-01-10</td></tr><tr><th>Summary</th><td>{summary}</td></tr><tr><th>Site</th><td>Mediterranean Sea off Elba <span class="geo">42.67833; 10.42722</span></td></tr></table>'
            row = article(html, "BOAC Flight 781", SOURCE)
            self.assertEqual(row["properties"]["event_type"], expected)
            self.assertEqual(row["geometry"] is not None, expected == "crash")

    def test_near_crash_has_no_impact_point(self):
        html = '<table class="infobox"><tr><th>Date</th><td>1981-02-20</td></tr><tr><th>Summary</th><td>Near crash into North Tower due to unauthorized descent</td></tr><tr><th>Site</th><td>North Tower <span class="geo">40.7; -74</span></td></tr></table>'
        row = article(html, "Aerolíneas Argentinas Flight 342", SOURCE)
        self.assertEqual(row["properties"]["event_type"], "incident")
        self.assertIsNone(row["geometry"])


class September11Tests(unittest.TestCase):
    def test_four_fatal_hijackings_are_mapped_crashes(self):
        from pipeline.articles import SEPTEMBER_11_FLIGHTS

        html = '<table class="infobox"><tr><th>Date</th><td>2001-09-11</td></tr><tr><th>Summary</th><td>Terrorist suicide hijacking</td></tr><tr><th>Site</th><td>Actual impact site <span class="geo">40.7; -74</span></td></tr></table>'
        for title in SEPTEMBER_11_FLIGHTS:
            row = article(html, title.replace(" ", "_"), SOURCE)
            self.assertEqual(row["properties"]["event_type"], "crash")
            self.assertIsNotNone(row["geometry"])
            self.assertIn("9/11", row["properties"]["search_aliases"])


class MilitaryListTests(unittest.TestCase):
    def test_dated_bullets_keep_serial_and_country_context(self):
        from pipeline.lists import parse_flexible

        html = '<h2 id="1975">1975</h2><ul><li>14 October 1975: F-15A, <b>73-0088</b>, USAF, crashed west of Minersville, Utah. Pilot ejected safely.</li></ul>'
        rows = parse_flexible(html, "List_of_F-15_losses", SOURCE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["properties"]["date"], "1975-10-14")
        self.assertEqual(rows[0]["properties"]["civil_or_military"], "military")
        self.assertEqual(
            rows[0]["properties"]["aircraft"][0]["registration"], "73-0088"
        )
        self.assertIsNone(rows[0]["geometry"])

    def test_event_tables_with_rowspan_do_not_parse_aircraft_totals(self):
        from pipeline.lists import parse_flexible

        html = '<table class="wikitable"><tr><th>Type</th><th>Destroyed</th></tr><tr><td>F-15</td><td>3</td></tr></table><table class="wikitable"><tr><th>Date</th><th>Variant</th><th>ID</th><th>Description</th></tr><tr><td rowspan="2">14 December 1961</td><td>P.1127</td><td>XP836</td><td>Crashed after a nozzle detached during the flight.</td></tr><tr><td>P.1127</td><td>XP837</td><td>A separate aircraft crashed during a landing.</td></tr></table>'
        rows = parse_flexible(html, "List_of_Harrier_family_losses", SOURCE)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["properties"]["date"] for r in rows], ["1961-12-14"] * 2)
        self.assertEqual(rows[1]["properties"]["aircraft"][0]["registration"], "XP837")

    def test_military_list_classification_survives_article_merge(self):
        a = event("Test crash", "2000-01-01", "", SOURCE, category="civil")
        b = event("Test crash", "2000-01-01", "", SOURCE, category="military")
        self.assertEqual(
            reconcile([a, b])[0]["properties"]["civil_or_military"], "military"
        )


class UpdateTests(unittest.TestCase):
    def test_changed_revision_bypasses_cached_article_response(self):
        import tempfile, hashlib, json
        from pathlib import Path
        from unittest.mock import Mock
        from pipeline.enrich import Wikimedia

        with tempfile.TemporaryDirectory() as temporary:
            client = Wikimedia()
            client.cache = Path(temporary)
            path = client.cache / (hashlib.sha256(b"Test").hexdigest() + ".json")
            path.write_text(
                json.dumps({"html": "old", "revision": 1, "retrieved_at": "old"})
            )
            client.current_revisions["Test"] = 2
            client.request = Mock(
                return_value={
                    "parse": {"text": {"*": "new"}, "revid": 2, "title": "Test"}
                }
            )
            self.assertEqual(client.fetch("Test")["html"], "new")
            self.assertTrue(client.request.call_args.kwargs["refresh"])

    def test_collision_extracts_military_aircraft_with_td_labels(self):
        html = '<table class="infobox"><tr><th>Date</th><td>1957-01-31</td></tr><tr><th>Site</th><td>Crash site <span class="geo">34; -118</span></td></tr><tr><td class="infobox-label">Aircraft type</td><td class="infobox-data">DC-7</td></tr><tr><td class="infobox-label">Operator</td><td class="infobox-data">Douglas</td></tr><tr><td class="infobox-label">Aircraft type</td><td class="infobox-data">F-89</td></tr><tr><td class="infobox-label">Operator</td><td class="infobox-data">United States Air Force</td></tr></table>'
        row = article(html, "Test_collision", SOURCE)
        self.assertEqual(len(row["properties"]["aircraft"]), 2)
        self.assertEqual(row["properties"]["civil_or_military"], "military")


class AircraftSectionTests(unittest.TestCase):
    def test_type_rows_under_aircraft_headers_capture_both_aircraft(self):
        html = '<table class="infobox"><tr><th>Date</th><td>1957-01-31</td></tr><tr><th class="infobox-header">First aircraft</th></tr><tr><th>Type</th><td>DC-7</td></tr><tr><th>Operator</th><td>Douglas</td></tr><tr><th class="infobox-header">Second aircraft</th></tr><tr><th>Type</th><td>F-89</td></tr><tr><th>Operator</th><td>United States Air Force</td></tr></table>'
        r = article(html, "Test_collision", SOURCE)
        self.assertEqual(
            [a["type"] for a in r["properties"]["aircraft"]], ["DC-7", "F-89"]
        )
        self.assertEqual(r["properties"]["civil_or_military"], "military")

    def test_engine_failure_with_safe_landing_has_no_crash_marker(self):
        html = '<div class="mw-parser-output"><table class="infobox"><tr><th>Date</th><td>2021-02-20</td></tr><tr><th>Summary</th><td>Engine failure caused by metal fatigue</td></tr><tr><th>Fatalities</th><td>0</td></tr><tr><th>Site</th><td>Over Colorado <span class="geo">40; -105</span></td></tr></table><p>The flight suffered an engine failure after takeoff and returned safely to the airport.</p></div>'
        r = article(html, "Test_Flight_328", SOURCE)
        self.assertEqual(r["properties"]["event_type"], "incident")
        self.assertIsNone(r["geometry"])
