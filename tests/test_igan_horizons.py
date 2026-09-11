from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IganHorizonsPageTests(unittest.TestCase):
    def test_event_pages_keep_current_official_destinations(self):
        pages = {
            ROOT / "igan-horizons-2026.html": "October 3, 2026",
            ROOT / "es/igan-horizons-2026.html": "3 de octubre de 2026",
        }

        for page, date in pages.items():
            content = page.read_text(encoding="utf-8")
            self.assertIn(date, content)
            self.assertIn("https://igan.org/events/igan-horizons/", content)
            self.assertIn("https://iganhorizons.vfairs.com/", content)
            self.assertIn("data-evt-loc=\"igan_horizons_page\"", content)

    def test_event_pages_describe_the_post_event_archival_plan(self):
        self.assertIn(
            "After the event, this page will remain as a dated resource",
            (ROOT / "igan-horizons-2026.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Después del evento, esta página seguirá disponible como recurso fechado",
            (ROOT / "es/igan-horizons-2026.html").read_text(encoding="utf-8"),
        )
