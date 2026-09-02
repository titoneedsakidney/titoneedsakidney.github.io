import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


def anchors_for(rel):
    parser = AnchorParser()
    parser.feed((ROOT / rel).read_text(encoding="utf-8"))
    return parser.anchors


class ConversionAnalyticsTests(unittest.TestCase):
    def assert_link(self, rel, href, cta_id, location):
        matches = [
            anchor for anchor in anchors_for(rel)
            if anchor.get("href") == href
        ]
        self.assertEqual(1, len(matches), f"expected one {href} link in {rel}")
        self.assertEqual(cta_id, matches[0].get("data-evt"))
        self.assertEqual(location, matches[0].get("data-evt-loc"))

    def test_primary_amazon_links_have_stable_ids_and_locations(self):
        cases = [
            ("book.html", "https://www.amazon.com/dp/B0DSXVL84P", "book_en_paperback", "book_page"),
            ("book.html", "https://www.amazon.com/dp/B0DT1N3FFG", "book_en_kindle", "book_page"),
            ("es/book.html", "https://www.amazon.com/dp/B0GCVN3YJW", "book_es_paperback", "book_page"),
            ("es/book.html", "https://www.amazon.com/dp/B0GCTHKNBR", "book_es_kindle", "book_page"),
            ("for-professionals.html", "https://www.amazon.com/dp/B0DSXVL84P", "book_en_paperback", "professional_page"),
            ("for-professionals.html", "https://www.amazon.com/dp/B0DT1N3FFG", "book_en_kindle", "professional_page"),
            ("es/para-profesionales.html", "https://www.amazon.com/dp/B0GCVN3YJW", "book_es_paperback", "professional_page"),
            ("es/para-profesionales.html", "https://www.amazon.com/dp/B0GCTHKNBR", "book_es_kindle", "professional_page"),
        ]
        for rel, href, cta_id, location in cases:
            with self.subTest(rel=rel, href=href):
                self.assert_link(rel, href, cta_id, location)

    def test_professional_entry_links_are_tracked_in_both_languages(self):
        self.assert_link("index.html", "/for-professionals.html", "professional_en", "homepage")
        self.assert_link("book.html", "/for-professionals.html", "professional_en", "book_page")
        self.assert_link("es/index.html", "/es/para-profesionales.html", "professional_es", "homepage")
        self.assert_link("es/book.html", "/es/para-profesionales.html", "professional_es", "book_page")

    def test_shared_footer_book_ctas_are_trackable_and_language_specific(self):
        self.assert_link("includes/footer.html", "/book.html", "book_en_info", None)
        self.assert_link("includes_es/footer.html", "/es/book.html", "book_es_info", None)
        for rel in ("includes/footer.html", "includes_es/footer.html"):
            self.assertIn('data-loc="site_footer"', (ROOT / rel).read_text(encoding="utf-8"))

    def test_analytics_listener_is_single_and_uses_only_link_metadata(self):
        script = (ROOT / "scripts/analytics.js").read_text(encoding="utf-8")
        self.assertEqual(1, script.count("document.addEventListener('click'"))
        self.assertIn("cta_click", script)
        self.assertIn("outbound_purchase", script)
        self.assertIn("view_book", script)
        self.assertIn("start_help_flow", script)
        self.assertIn("browse_organizations", script)
        self.assertIn("data-evt-loc", script)
        self.assertNotIn("cta_text", script)
        self.assertNotIn("link_url", script)
        self.assertNotIn("data-email", script)
        self.assertNotIn("FormData", script)

    def test_ga_loader_appears_once_on_each_conversion_page(self):
        for rel in ("index.html", "es/index.html", "book.html", "es/book.html",
                    "for-professionals.html", "es/para-profesionales.html"):
            with self.subTest(rel=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(1, text.count("googletagmanager.com/gtag/js"))


if __name__ == "__main__":
    unittest.main()
