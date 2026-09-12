from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summarize_search_console.py"
SPEC = importlib.util.spec_from_file_location("summarize_search_console", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class SearchConsoleOpportunityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_csv(self, text: str) -> Path:
        path = self.root / "search-console.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_redacts_queries_by_default_and_filters_candidates(self) -> None:
        path = self.write_csv(
            "Query,Page,Clicks,Impressions,CTR,Position\n"
            "kidney donor info,https://titoneedsakidney.com/donor-info.html,0,80,0%,4.5\n"
            "book title,https://titoneedsakidney.com/book.html,20,100,20%,3.0\n"
            "deep result,https://titoneedsakidney.com/about.html,0,100,0%,18.0\n"
            "tiny sample,https://titoneedsakidney.com/about.html,0,10,0%,4.0\n"
        )
        rows, has_page = mod.read_rows(path)
        report = mod.build_report(
            rows,
            has_page=has_page,
            min_impressions=25,
            max_ctr=0.05,
            max_position=10,
            include_query_text=False,
        )
        self.assertEqual(report["candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertNotIn("query", candidate)
        self.assertEqual(candidate["page"], "/donor-info.html")
        self.assertEqual(candidate["impressions"], 80)
        self.assertEqual(candidate["clicks"], 0)
        self.assertEqual(report["page_summary"][0]["candidate_count"], 1)

    def test_explicit_private_mode_includes_query_and_aggregates_duplicates(self) -> None:
        path = self.write_csv(
            "Top queries,Top pages,Clicks,Impressions,CTR,Average position\n"
            "kidney help,/about.html,1,40,2.5%,4\n"
            "kidney help,/about.html,1,60,1.67%,6\n"
        )
        rows, has_page = mod.read_rows(path)
        report = mod.build_report(
            rows,
            has_page=has_page,
            min_impressions=25,
            max_ctr=0.05,
            max_position=10,
            include_query_text=True,
        )
        self.assertEqual(report["candidate_count"], 1)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["query"], "kidney help")
        self.assertEqual(candidate["impressions"], 100)
        self.assertEqual(candidate["clicks"], 2)
        self.assertAlmostEqual(candidate["ctr"], 0.02)
        self.assertAlmostEqual(candidate["position"], 5.2)

    def test_rejects_identifier_columns(self) -> None:
        path = self.write_csv(
            "Query,Clicks,Impressions,Position,session_id\n"
            "kidney,0,40,3,abc\n"
        )
        with self.assertRaisesRegex(mod.SearchConsoleReportError, "identifier"):
            mod.read_rows(path)

    def test_rejects_inconsistent_counts(self) -> None:
        path = self.write_csv(
            "Query,Clicks,Impressions,CTR,Position\n"
            "kidney,6,5,120%,3\n"
        )
        with self.assertRaisesRegex(mod.SearchConsoleReportError, "clicks must not exceed"):
            mod.read_rows(path)

    def test_observation_window_is_strict(self) -> None:
        path = self.write_csv(
            "Query,Clicks,Impressions,CTR,Position\n"
            "kidney,0,40,0%,3\n"
        )
        rows, has_page = mod.read_rows(path)
        with self.assertRaisesRegex(mod.SearchConsoleReportError, "supplied together"):
            mod.build_report(
                rows,
                has_page=has_page,
                min_impressions=25,
                max_ctr=0.05,
                max_position=10,
                include_query_text=False,
                window_start="2026-09-01",
            )
        with self.assertRaisesRegex(mod.SearchConsoleReportError, "must not be after"):
            mod.build_report(
                rows,
                has_page=has_page,
                min_impressions=25,
                max_ctr=0.05,
                max_position=10,
                include_query_text=False,
                window_start="2026-09-10",
                window_end="2026-09-01",
            )

    def test_cli_smoke_outputs_stable_redacted_json(self) -> None:
        path = self.write_csv(
            "Query,Page,Clicks,Impressions,CTR,Position\n"
            "private query,https://titoneedsakidney.com/about.html?x=1,1,50,2%,4.5\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                str(path),
                "--window-start",
                "2026-09-01",
                "--window-end",
                "2026-09-07",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "FACTS_READY")
        self.assertFalse(payload["query_text_included"])
        self.assertNotIn("private query", result.stdout)
        self.assertEqual(payload["candidates"][0]["page"], "/about.html")
        self.assertEqual(
            payload["observation_window"],
            {"start": "2026-09-01", "end": "2026-09-07"},
        )


if __name__ == "__main__":
    unittest.main()
