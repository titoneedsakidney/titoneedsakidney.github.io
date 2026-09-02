import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPES = ROOT / "includes" / "prototypes" / "issue-19"
MODELS = ("a2.html", "b.html", "c.html")
JOURNEY_ANCHORS = (
    "transplant-nephrologist",
    "other-transplant-roles",
    "dialysis",
    "dialysis-social-worker",
    "caregiver",
)


class Issue19PrototypeTests(unittest.TestCase):
    def test_three_nonproduction_bilingual_models_have_core_journey_routes(self):
        for name in MODELS:
            text = (PROTOTYPES / name).read_text(encoding="utf-8")
            with self.subTest(model=name):
                self.assertIn('name="robots" content="noindex, nofollow"', text)
                self.assertIn('lang="es"', text)
                self.assertIn("You may also find these helpful", text)
                self.assertNotIn("utm_", text)
                for anchor in JOURNEY_ANCHORS:
                    self.assertIn(anchor, text)

    def test_review_index_has_the_three_models_and_eight_journey_checks(self):
        text = (PROTOTYPES / "index.html").read_text(encoding="utf-8")
        for name in MODELS:
            self.assertIn(name, text)
        self.assertIn("Eight journey checks", text)
        self.assertIn("Spanish visitor completes the same routes", text)
        self.assertIn("Side-by-side desk-test scorecard", text)


if __name__ == "__main__":
    unittest.main()
