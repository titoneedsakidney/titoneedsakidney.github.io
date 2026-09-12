import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import summarize_ga4_exploration_export as module
import summarize_ga4_transitions as core


class NativeExplorationExportTests(unittest.TestCase):
    def write_text(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", delete=False
        )
        with handle:
            handle.write(text)
        return Path(handle.name)

    def test_reads_google_comments_friendly_headers_and_grand_total(self):
        path = self.write_text(
            "# ----------------------------------------\n"
            "# Tito needs a kidney\n"
            "# page referrer export-Free form 1\n"
            "# 20260814-20260910\n"
            "# ----------------------------------------\n"
            "\n"
            "Hostname,Page referrer,Page path + query string,Views\n"
            ",,,21,Grand total\n"
            "titoneedsakidney.com,,/,10\n"
            "titoneedsakidney.com,https://titoneedsakidney.com/,/book.html?utm_source=x,4\n"
            "127.0.0.1,,,7\n"
        )

        rows = module.load_native_rows(path)
        self.assertEqual(3, len(rows))
        report = core.build_report(rows, min_page_views=1, min_transition_views=1)
        self.assertEqual(14, report["production_page_views"])
        self.assertEqual(7, report["ignored_nonproduction_views"])
        self.assertIn(
            {"from": "/", "to": "/book.html", "views": 4},
            report["top_transitions"],
        )

    def test_accepts_canonical_api_style_headers_too(self):
        path = self.write_text(
            "hostName,pageReferrer,pagePath,screenPageViews\n"
            "titoneedsakidney.com,,/,3\n"
        )
        rows = module.load_native_rows(path)
        self.assertEqual(1, len(rows))
        self.assertEqual(3, rows[0].views)

    def test_refuses_visitor_identifier_columns(self):
        path = self.write_text(
            "Hostname,Page referrer,Page path + query string,Views,User pseudo ID\n"
            "titoneedsakidney.com,,/,3,abc\n"
        )
        with self.assertRaisesRegex(core.InputError, "identifier columns"):
            module.load_native_rows(path)

    def test_unexpected_extra_columns_fail_closed(self):
        path = self.write_text(
            "Hostname,Page referrer,Page path + query string,Views\n"
            "titoneedsakidney.com,,/,3,unexpected\n"
        )
        with self.assertRaisesRegex(core.InputError, "unexpected column count"):
            module.load_native_rows(path)


if __name__ == "__main__":
    unittest.main()
