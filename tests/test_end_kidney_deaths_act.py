from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EndKidneyDeathsActPageTests(unittest.TestCase):
    def test_bilingual_pages_keep_the_official_bill_and_campaign_sources(self):
        pages = [
            ROOT / "end-kidney-deaths-act.html",
            ROOT / "es/end-kidney-deaths-act.html",
        ]

        for page in pages:
            content = page.read_text(encoding="utf-8")
            self.assertIn("H.R. 2687", content)
            self.assertIn(
                "https://www.govinfo.gov/app/details/BILLS-119hr2687ih",
                content,
            )
            self.assertIn("https://www.endkidneydeathsact.org/", content)
            self.assertIn("https://www.waitlistzero.org/", content)
            self.assertIn("data-evt-loc=\"ekda_page\"", content)

    def test_bilingual_transplant_hubs_link_to_the_policy_resource(self):
        self.assertIn(
            "/end-kidney-deaths-act.html",
            (ROOT / "hub/transplant/index.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "/es/end-kidney-deaths-act.html",
            (ROOT / "es/hub/transplant/index.html").read_text(encoding="utf-8"),
        )
