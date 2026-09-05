import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BookAvailabilityTests(unittest.TestCase):
    def test_english_page_lists_only_verified_published_channels(self):
        text = (ROOT / "book.html").read_text(encoding="utf-8")

        for channel in (
            "Apple",
            "Barnes &amp; Noble",
            "Fable",
            "Gardners",
            "Kobo",
            "Smashwords",
            "Tolino",
            "Vivlio (for sale and library)",
            "BorrowBox, OverDrive, or Vivlio",
        ):
            with self.subTest(channel=channel):
                self.assertIn(channel, text)

        self.assertNotIn("Hoopla", text)
        self.assertNotIn("cloudLibrary", text)

    def test_spanish_page_lists_only_verified_published_channels(self):
        text = (ROOT / "es/book.html").read_text(encoding="utf-8")

        for channel in (
            "Apple",
            "Barnes &amp; Noble",
            "BorrowBox",
            "cloudLibrary",
            "Fable",
            "Kobo",
            "OverDrive",
            "Smashwords",
            "Tolino",
            "Vivlio (para venta y bibliotecas)",
        ):
            with self.subTest(channel=channel):
                self.assertIn(channel, text)

        self.assertNotIn("Hoopla", text)

    def test_pages_explain_why_unverified_direct_listing_urls_are_omitted(self):
        self.assertIn(
            "Individual retailer and library-catalog links are added only after the exact edition page",
            (ROOT / "book.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Los enlaces a tiendas individuales y catálogos de bibliotecas se agregarán solo después",
            (ROOT / "es/book.html").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
