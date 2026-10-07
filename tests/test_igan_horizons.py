from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IganResourceMigrationTests(unittest.TestCase):
    def test_evergreen_foundation_pages_link_to_current_official_resources(self):
        pages = [
            ROOT / "igan-foundation.html",
            ROOT / "es/igan-foundation.html",
        ]

        for page in pages:
            content = page.read_text(encoding="utf-8")
            self.assertIn("https://igan.org/", content)
            self.assertIn("https://igan.org/iga-nephropathy-guide/", content)
            self.assertIn("https://igan.org/support-options/", content)
            self.assertIn("https://igan.org/apply-for-patient-aid/", content)
            self.assertIn('data-evt-loc="igan_foundation_page"', content)

    def test_old_event_pages_are_retired_but_keep_a_handoff(self):
        cases = {
            ROOT / "igan-horizons-2026.html": (
                "https://titoneedsakidney.com/igan-foundation.html",
                "/igan-foundation.html",
                "has ended",
            ),
            ROOT / "es/igan-horizons-2026.html": (
                "https://titoneedsakidney.com/es/igan-foundation.html",
                "/es/igan-foundation.html",
                "finalizó",
            ),
        }

        for page, (canonical, handoff, ended_text) in cases.items():
            content = page.read_text(encoding="utf-8")
            self.assertIn('<meta name="robots" content="noindex,follow">', content)
            self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
            self.assertIn(f'href="{handoff}"', content)
            self.assertIn(ended_text, content)

    def test_current_entry_points_no_longer_promote_horizons(self):
        for rel in ("index.html", "book.html", "es/index.html", "es/book.html"):
            with self.subTest(rel=rel):
                content = (ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("igan-horizons-2026.html", content)
                self.assertIn("igan-foundation.html", content)

    def test_patient_navigator_directory_has_durable_entry_points(self):
        url = "https://patient-navigator-hub.replit.app/"
        cases = {
            "index.html": "resource_en_patient_navigator",
            "hub/index.html": "resource_en_patient_navigator",
            "es/index.html": "resource_es_patient_navigator",
            "es/hub/index.html": "resource_es_patient_navigator",
        }

        for rel, event_id in cases.items():
            with self.subTest(rel=rel):
                content = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(url, content)
                self.assertIn(f'data-evt="{event_id}"', content)


if __name__ == "__main__":
    unittest.main()
