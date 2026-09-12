import csv
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import summarize_ga4_transitions as module


class TransitionSummaryTests(unittest.TestCase):
    def write_csv(self, rows, fieldnames=None):
        handle = tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", delete=False
        )
        fieldnames = fieldnames or [
            "hostName",
            "pageReferrer",
            "pagePath",
            "screenPageViews",
        ]
        with handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return Path(handle.name)

    def test_classifies_entries_transitions_reloads_and_nonproduction(self):
        path = self.write_csv(
            [
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "",
                    "pagePath": "/",
                    "screenPageViews": "10",
                },
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://titoneedsakidney.com/?utm_source=x",
                    "pagePath": "/book.html",
                    "screenPageViews": "4",
                },
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://titoneedsakidney.com/book.html#availability",
                    "pagePath": "/book.html",
                    "screenPageViews": "2",
                },
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://www.google.com/search?q=kidney",
                    "pagePath": "/es/",
                    "screenPageViews": "3",
                },
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://titoneedsakidney.com/hub/index.html",
                    "pagePath": "/hub/dialysis/index.html",
                    "screenPageViews": "5",
                },
                {
                    "hostName": "127.0.0.1",
                    "pageReferrer": "",
                    "pagePath": "/",
                    "screenPageViews": "7",
                },
            ]
        )
        report = module.build_report(
            module.load_rows(path), min_page_views=1, min_transition_views=1
        )
        self.assertEqual(24, report["production_page_views"])
        self.assertEqual(7, report["ignored_nonproduction_views"])
        self.assertEqual(13, report["entry_or_external_referrer_views"])
        self.assertEqual(9, report["same_site_transition_views"])
        self.assertEqual(2, report["same_page_referrer_views"])
        self.assertIn(
            {"from": "/hub/", "to": "/hub/dialysis/", "views": 5},
            report["top_transitions"],
        )
        self.assertIn(
            {"from": "/", "to": "/book.html", "views": 4},
            report["top_transitions"],
        )

    def test_refuses_visitor_level_identifier_columns(self):
        path = self.write_csv(
            [
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "",
                    "pagePath": "/",
                    "screenPageViews": "1",
                    "userPseudoId": "abc",
                },
            ],
            fieldnames=[
                "hostName",
                "pageReferrer",
                "pagePath",
                "screenPageViews",
                "userPseudoId",
            ],
        )
        with self.assertRaisesRegex(module.InputError, "identifier columns"):
            module.load_rows(path)

    def test_rejects_negative_or_fractional_aggregate_counts(self):
        for value in ("-1", "1.5"):
            with self.subTest(value=value):
                path = self.write_csv(
                    [
                        {
                            "hostName": "titoneedsakidney.com",
                            "pageReferrer": "",
                            "pagePath": "/",
                            "screenPageViews": value,
                        },
                    ]
                )
                with self.assertRaisesRegex(module.InputError, "non-negative integer"):
                    module.load_rows(path)

    def test_markdown_keeps_dead_end_interpretation_cautious(self):
        path = self.write_csv(
            [
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "",
                    "pagePath": "/about.html",
                    "screenPageViews": "8",
                },
            ]
        )
        markdown = module.render_markdown(
            module.build_report(
                module.load_rows(path), min_page_views=1, min_transition_views=1
            )
        )
        self.assertIn("not an exit-rate calculation", markdown)
        self.assertIn("`/about.html`", markdown)
        self.assertNotIn("8 exits", markdown)

    def test_low_count_transitions_are_suppressed_from_ranked_output(self):
        path = self.write_csv(
            [
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://titoneedsakidney.com/",
                    "pagePath": "/book.html",
                    "screenPageViews": "2",
                },
                {
                    "hostName": "titoneedsakidney.com",
                    "pageReferrer": "https://titoneedsakidney.com/",
                    "pagePath": "/hub/",
                    "screenPageViews": "3",
                },
            ]
        )
        report = module.build_report(module.load_rows(path))
        self.assertEqual(1, report["suppressed_low_count_transition_pairs"])
        self.assertEqual(
            [{"from": "/", "to": "/hub/", "views": 3}],
            report["top_transitions"],
        )


if __name__ == "__main__":
    unittest.main()
