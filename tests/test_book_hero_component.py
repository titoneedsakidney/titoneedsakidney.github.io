import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAIRS = (
    ("book.html", "includes/book-hero.html", "en"),
    ("es/book.html", "includes_es/book-hero.html", "es"),
)


def normalize_html(text: str) -> str:
    """Normalize insignificant inter-tag/text whitespace for parity checks."""
    return re.sub(r"\s+", " ", text.strip())


class BookHeroComponentTests(unittest.TestCase):
    def test_staged_components_match_current_rendered_hero(self):
        """The staged Lego must remain semantically identical to the live-page hero."""
        for page_path, include_path, _language in PAIRS:
            with self.subTest(page=page_path):
                page = normalize_html((ROOT / page_path).read_text(encoding="utf-8"))
                fragment = normalize_html((ROOT / include_path).read_text(encoding="utf-8"))
                self.assertIn(fragment, page)

    def test_components_preserve_required_book_hero_contract(self):
        for _page_path, include_path, language in PAIRS:
            with self.subTest(include=include_path):
                fragment = (ROOT / include_path).read_text(encoding="utf-8")
                self.assertEqual(fragment.count('class="book-hero"'), 1)
                self.assertEqual(fragment.count("<h1>"), 1)
                self.assertIn('fetchpriority="high"', fragment)
                self.assertIn('decoding="async"', fragment)
                for width in (320, 520, 800):
                    self.assertRegex(fragment, rf"book-cover-{language}-{width}\\.webp")
                self.assertGreaterEqual(fragment.count('data-evt-loc="'), 3)
                self.assertIn('href="#availability"', fragment)

    def test_components_keep_language_switch_and_purchase_events_distinct(self):
        english = (ROOT / "includes/book-hero.html").read_text(encoding="utf-8")
        spanish = (ROOT / "includes_es/book-hero.html").read_text(encoding="utf-8")

        for event in ("book_en_paperback", "book_en_kindle", "book_en_availability"):
            self.assertIn(f'data-evt="{event}"', english)
            self.assertNotIn(f'data-evt="{event}"', spanish)
        for event in ("book_es_paperback", "book_es_kindle", "book_es_availability"):
            self.assertIn(f'data-evt="{event}"', spanish)
            self.assertNotIn(f'data-evt="{event}"', english)

        self.assertIn('href="/es/book.html" hreflang="es" lang="es"', english)
        self.assertIn('href="/book.html" hreflang="en" lang="en"', spanish)


if __name__ == "__main__":
    unittest.main()
