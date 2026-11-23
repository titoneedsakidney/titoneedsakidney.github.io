import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPES = ROOT / "includes" / "prototypes" / "issue-19"
MODELS = {
    "a2": {"en": "a2.html", "es": "a2-es.html"},
    "b": {"en": "b.html", "es": "b-es.html"},
    "c": {"en": "c.html", "es": "c-es.html"},
}
ENGLISH_JOURNEY_MARKERS = (
    'id="transplant-nephrologist"',
    'id="other-transplant-roles"',
    'id="dialysis-social-worker"',
    'id="caregiver"',
    "You may also find these helpful",
)
SPANISH_JOURNEY_MARKERS = (
    'id="transplant-nephrologist"',
    'id="other-transplant-roles"',
    'id="trabajador-social-dialisis"',
    'id="cuidador"',
    "También puede ser útil",
)


class Issue19PrototypeTests(unittest.TestCase):
    def test_each_model_has_independent_english_and_spanish_previews(self):
        for model, pages in MODELS.items():
            english = (PROTOTYPES / pages["en"]).read_text(encoding="utf-8")
            spanish = (PROTOTYPES / pages["es"]).read_text(encoding="utf-8")
            with self.subTest(model=model, language="en"):
                self.assertIn('<html lang="en">', english)
                self.assertIn('name="robots" content="noindex, nofollow"', english)
                self.assertIn('book-cover-en-320.webp', english)
                self.assertIn('class="first-screen"', english)
                self.assertIn(f'href="{pages["es"]}"', english)
                self.assertNotIn("utm_", english)
                for marker in ENGLISH_JOURNEY_MARKERS:
                    self.assertIn(marker, english)
            with self.subTest(model=model, language="es"):
                self.assertIn('<html lang="es">', spanish)
                self.assertIn('name="robots" content="noindex, nofollow"', spanish)
                self.assertIn('book-cover-es-320.webp', spanish)
                self.assertIn('class="first-screen"', spanish)
                self.assertIn(f'href="{pages["en"]}"', spanish)
                self.assertNotIn("utm_", spanish)
                for marker in SPANISH_JOURNEY_MARKERS:
                    self.assertIn(marker, spanish)

    def test_first_screen_keeps_book_and_help_paths_together(self):
        for pages in MODELS.values():
            for filename in pages.values():
                text = (PROTOTYPES / filename).read_text(encoding="utf-8")
                first_screen = text.split('class="first-screen"', 1)[1].split('</section>', 1)[0]
                with self.subTest(page=filename):
                    self.assertIn('class="book-identity"', first_screen)
                    self.assertIn('class="pathway-intro"', first_screen)
                    self.assertIn('class="cards"', first_screen)
                    self.assertGreaterEqual(first_screen.count('class="card"'), 5)

    def test_each_preview_has_no_dead_internal_anchor(self):
        for pages in MODELS.values():
            for filename in pages.values():
                text = (PROTOTYPES / filename).read_text(encoding="utf-8")
                ids = set(re.findall(r'\bid="([^"]+)"', text))
                anchors = set(re.findall(r'href="#([^"]+)"', text))
                with self.subTest(page=filename):
                    self.assertTrue(anchors)
                    self.assertTrue(anchors <= ids, anchors - ids)

    def test_review_index_links_all_six_previews_and_the_eight_journeys(self):
        text = (PROTOTYPES / "index.html").read_text(encoding="utf-8")
        for pages in MODELS.values():
            for filename in pages.values():
                self.assertIn(f'href="{filename}"', text)
        self.assertIn("Eight journey checks", text)
        self.assertIn("Spanish visitor completes the same routes", text)
        self.assertIn("Side-by-side desk-test scorecard", text)


if __name__ == "__main__":
    unittest.main()
