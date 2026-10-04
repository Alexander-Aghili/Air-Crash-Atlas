import unittest
from pipeline.source_entries import enumerate_entries, parse_unusual
from pipeline.extract import event, reconcile, URL
from pipeline.articles import article
from pipeline.audit import audit


class SourceEntryAuditTests(unittest.TestCase):
    source = {'url': URL('List_of_aviation_accidents'), 'revision': 1}

    def test_identical_source_text_under_different_dates_is_not_silently_skipped(self):
        html = '<h2>1950</h2><dl><dt>5 January</dt><dd>An unidentified aircraft crashed at an airfield.</dd><dt>6 January</dt><dd>An unidentified aircraft crashed at an airfield.</dd></dl>'
        entries = enumerate_entries(html, 'List_of_aviation_accidents')
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]['review_reason'], 'duplicate_source_text_requires_context_review')
        self.assertEqual(entries[1]['source_position'], 2)

    def test_heading_year_outweighs_recovery_year_and_flight_number(self):
        from pipeline.source_entries import date_text
        self.assertEqual(date_text("March 21 – An aircraft disappeared; its wreckage was found in 1958.", "1931"), "1931-03-21")
        self.assertEqual(date_text("September 12 – Air France Flight 2005 crashed at an airport.", "1961"), "1961-09-12")

    def test_flight_numbers_are_not_years(self):
        from pipeline.source_entries import date_text
        self.assertIsNone(date_text('Example Flight 1862 crashed.'))
        self.assertEqual(date_text('Example Flight 1862 crashed in 1992.'), '1992')
        self.assertEqual(date_text('September 12 – Example Flight 2005 crashed.', '1961'), '1961-09-12')

    def test_summary_of_several_years_is_not_published_as_one_event(self):
        html = '<p>The deadliest crash was Example Flight 1862. Other aircraft crashed in 1946, 1980 and 1993.</p>'
        entries = enumerate_entries(html, 'List_of_aviation_accidents')
        self.assertEqual(entries[0]['review_reason'], 'multiple_event_dates_in_one_entry')
        self.assertIsNone(entries[0]['date'])
        self.assertEqual(parse_unusual(html, 'List_of_aviation_accidents', self.source, []), [])

    def test_month_and_season_definition_dates_retain_source_precision(self):
        html = '<h2>1950</h2><dl><dt>February</dt><dd>A Navy aircraft crashed at an airfield.</dd><dt>Summer</dt><dd>A second Navy aircraft crashed at another airfield.</dd></dl>'
        entries = enumerate_entries(html, "List_of_aviation_accidents")
        self.assertEqual([e["date"] for e in entries], ["1950-02", "1950"])
        self.assertTrue(all(e["review_reason"] is None for e in entries))

    def test_year_definition_heading_overrides_decade_for_following_bullets(self):
        from pipeline.lists import parse_flexible
        html = '<h2>2020s</h2><dl><dt>2025</dt></dl><ul><li>29 January – A passenger aircraft collided with a military helicopter.</li></ul>'
        self.assertEqual(enumerate_entries(html, 'List_of_aviation_accidents')[0]['date'], '2025-01-29')
        self.assertEqual(parse_flexible(html, 'List_of_aviation_accidents', self.source)[0]['properties']['date'], '2025-01-29')

    def test_short_definition_dates_are_kept_and_do_not_leak_between_entries(self):
        html = '<h2>1950</h2><dl><dt>5 January</dt><dd>A Navy aircraft crashed at an airfield.</dd><dt>6 January</dt><dd>A second Navy aircraft crashed at another airfield.</dd></dl>'
        entries = enumerate_entries(html, "List_of_aviation_accidents")
        self.assertEqual([e["date"] for e in entries], ["1950-01-05", "1950-01-06"])

    def test_full_definition_dates_do_not_need_year_headings(self):
        html = '<dl><dt>17 November 1950</dt><dd>A Douglas DC-3 aircraft crashed during its approach.</dd></dl>'
        rows = parse_unusual(html, 'List_of_aviation_accidents', self.source, [])
        self.assertEqual(rows[0]['properties']['date'], '1950-11-17')
        from pipeline.extract import parse_list
        legacy = parse_list(html, "List_of_aviation_accidents", self.source)
        self.assertEqual(legacy[0]["properties"]["date"], "1950-11-17")
        self.assertEqual(rows[0]['properties']['source_entries'][0]['entry_id'], enumerate_entries(html, 'List_of_aviation_accidents')[0]['entry_id'])

    def test_headerless_table_with_one_unambiguous_date_cell_is_supported(self):
        html = '<table><tr><td>Russian Army</td><td>August 2014</td><td>An aircraft was shot down.</td></tr><tr><td>22 Apr 1977</td><td>Convair CV-440 crashed.</td></tr></table>'
        rows = parse_unusual(html, 'List_of_aviation_accidents', self.source, [])
        self.assertEqual([row['properties']['date'] for row in rows], ['2014-08', '1977-04-22'])

    def test_multilevel_headers_and_rowspan_preserve_date_column(self):
        html = '<table class="wikitable"><tr><th colspan="2">Deaths</th><th rowspan="2">Accident date</th><th rowspan="2">Aircraft</th></tr><tr><th>Total</th><th>Crew</th></tr><tr><th>4</th><th>2</th><td rowspan="2">1950-11-17</td><td>A DC-3 crashed</td></tr><tr><th>3</th><th>1</th><td>A second aircraft crashed</td></tr></table>'
        rows = parse_unusual(html, 'List_of_aviation_accidents', self.source, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['properties']['date'] for r in rows], ['1950-11-17'] * 2)
        self.assertEqual(rows[0]['properties']['raw_list_fields']['aircraft'], 'A DC-3 crashed')

    def test_prose_month_precision_and_nested_bullets(self):
        html = '<h2>1910s</h2><p>In May 1917, a French seaplane crashed, killing the pilot.</p><ul><li>Aircraft losses<ul><li>First loss: a plane crashed on 29 August 1964 near an airbase.</li></ul></li></ul>'
        rows = parse_unusual(html, 'List_of_aviation_accidents', self.source, [])
        self.assertEqual([r['properties']['date'] for r in rows], ['1917-05', '1964-08-29'])

    def test_aggregate_totals_and_reference_lists_are_not_events(self):
        html = '<table class="wikitable"><tr><th>Aircraft</th><th>Destroyed</th></tr><tr><td>F-15</td><td>19</td></tr></table><div class="reflist"><ul><li>A crash report from 1964 was published in 2000.</li></ul></div>'
        self.assertEqual(enumerate_entries(html, 'List_of_aviation_accidents'), [])

    def test_compound_narrative_remains_a_review_issue(self):
        html = '<p>An aircraft crashed on 29 August 1964 and another aircraft crashed on 30 August 1964.</p>'
        entries = enumerate_entries(html, 'List_of_aviation_accidents')
        self.assertEqual(entries[0]['review_reason'], 'multiple_event_dates_in_one_entry')
        self.assertEqual(parse_unusual(html, 'List_of_aviation_accidents', self.source, []), [])

    def test_audit_flags_a_related_article_from_another_year(self):
        from pipeline.extract import SEEDS
        class FixtureFetcher:
            def fetch(self, title):
                return {'html': '<h2>1996</h2><ul><li>8 January 1996: a military aircraft crashed; a survivor later died on another flight.</li></ul>', 'revision': 1, 'retrieved_at': 'test'}
        listed = event('Flight 11', '1996-01-08', '8 January 1996: a military aircraft crashed; a survivor later died on another flight.', {'url': URL(SEEDS[0])})
        listed['properties']['article_titles'] = ['Flight_11']
        dedicated = event('Flight 11', '2001-09-11', '', {'url': URL('Flight_11')})
        dedicated['properties'].update(article_url=URL('Flight_11'), article_titles=['Flight_11'])
        report = audit([dedicated, listed], FixtureFetcher())
        flagged = [entry for entry in report['entries'] if entry['status'] == 'needs_review']
        self.assertEqual(len(flagged), 1)
        self.assertIn('different_event_year', flagged[0]['reason'])

    def test_audit_does_not_count_article_link_as_proof_for_another_entry(self):
        from pipeline.extract import SEEDS
        class FixtureFetcher:
            def fetch(self, title):
                return {'html': '<h2>1964</h2><ul><li>29 August 1964: a plane crashed.</li><li>30 August 1964: a plane crashed.</li></ul>', 'revision': 1, 'retrieved_at': 'test'}
        record = event('Test', '1964-08-29', '29 August 1964: a plane crashed.', {'url': URL(SEEDS[0]), 'revision': 1})
        report = audit([record], FixtureFetcher())
        self.assertEqual(report['summary']['matched'], 1)
        self.assertEqual(report['summary']['missing'], 2 * len(SEEDS) - 1)
        self.assertEqual(report['summary']['matched_entries_without_coordinates'], 1)

    def test_related_accident_links_do_not_merge_distinct_events(self):
        from pipeline.extract import parse_civil
        html = '<h2>1967</h2><ul><li>March 9 – <a href="/wiki/First_Flight_553">Flight 553</a> crashed, an accident later compared to <a href="/wiki/Other_Flight_22">Flight 22</a>.</li><li>July 19 – <a href="/wiki/Other_Flight_22">Flight 22</a> crashed in another city.</li></ul>'
        rows = parse_civil(html, "List_of_accidents_involving_commercial_aircraft", self.source)
        self.assertEqual(rows[0]["properties"]["article_titles"], ["First_Flight_553"])
        self.assertEqual(rows[0]["properties"]["related_article_titles"], ["Other_Flight_22"])
        self.assertEqual(len(reconcile(rows)), 2)

    def test_redirect_alias_merges_source_entry_into_canonical_article(self):
        primary = event("Canonical crash", "1950-11-17", "", {"url": URL("Canonical_crash")})
        primary["properties"]["article_titles"] = ["Old_crash_name", "Canonical_crash"]
        shallow = event("Old crash name", "1950-11-17", "A plane crashed", self.source, aircraft=[{"registration": "N123"}])
        shallow["properties"]["article_titles"] = ["Old_crash_name"]
        rows = reconcile([primary, shallow])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["properties"]["source_entries"]), 1)
        self.assertEqual(rows[0]["properties"]["aircraft"][0]["registration"], "N123")

    def test_operator_evidence_survives_wrong_list_category(self):
        html = '<div class="mw-parser-output"><p>A commercial flight crashed near an Army airfield on 17 November 1950.</p><table class="infobox"><tr><th>Date</th><td>17 November 1950</td></tr><tr><th>Aircraft type</th><td>DC-3</td></tr><tr><th>Operator</th><td>Example Airlines</td></tr></table></div>'
        primary = article(html, 'Example crash', {'url': 'https://en.wikipedia.org/wiki/Example_crash'})
        shallow = event('Example crash', '1950-11-17', '', self.source, category='military')
        self.assertEqual(reconcile([primary, shallow])[0]['properties']['civil_or_military'], 'civil')
        for order in [[primary, shallow], [shallow, primary]]:
            self.assertEqual(reconcile(order)[0]['properties']['civil_or_military'], 'civil')

    def test_article_without_infobox_reads_date_and_military_from_lead(self):
        row = article('<p>On May 16, 1946, a U.S. Army aircraft crashed into a hill near a small town.</p>', 'Example crash', {'url': 'https://en.wikipedia.org/wiki/Example_crash'})
        self.assertEqual(row['properties']['date'], '1946-05-16')
        self.assertEqual(row['properties']['civil_or_military'], 'military')
