import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_navigation_paths.py"
SPEC = importlib.util.spec_from_file_location("audit_navigation_paths", MODULE_PATH)
nav = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(nav)


class NavigationPathAuditTests(unittest.TestCase):
    def test_shortest_path_prefers_direct_link(self):
        graph = {
            "index.html": {"about.html", "hub/index.html"},
            "about.html": {"deep.html"},
            "hub/index.html": {"deep.html"},
            "deep.html": set(),
        }
        distances, previous = nav.shortest_paths(graph, "index.html")
        self.assertEqual(distances["deep.html"], 2)
        self.assertIn(nav.reconstruct_path(previous, "deep.html"), [
            ["index.html", "about.html", "deep.html"],
            ["index.html", "hub/index.html", "deep.html"],
        ])

    def test_report_marks_unreachable_pages(self):
        graph = {
            "index.html": {"about.html"},
            "about.html": set(),
            "orphan.html": set(),
        }
        report = nav.build_report(graph, ["index.html"])
        entry = report["entries"][0]
        self.assertEqual(entry["reachable_page_count"], 2)
        self.assertEqual(entry["unreachable_pages"], ["orphan.html"])
        self.assertEqual(entry["max_clicks"], 1)
        self.assertEqual(report["zero_incoming_pages"], ["index.html", "orphan.html"])

    def test_multiple_entry_points_are_reported_independently(self):
        graph = {
            "index.html": {"es/index.html", "about.html"},
            "about.html": set(),
            "es/index.html": {"es/about.html"},
            "es/about.html": set(),
        }
        report = nav.build_report(graph, ["index.html", "es/index.html"])
        self.assertEqual(report["entries"][0]["max_clicks"], 2)
        self.assertEqual(report["entries"][1]["reachable_page_count"], 2)
        self.assertEqual(report["entries"][1]["unreachable_page_count"], 2)

    def test_unknown_entry_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "entry page"):
            nav.shortest_paths({"index.html": set()}, "missing.html")


if __name__ == "__main__":
    unittest.main()
