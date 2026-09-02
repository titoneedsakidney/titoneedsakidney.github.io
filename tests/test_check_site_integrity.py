import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_site_integrity as integrity


class IntegrityCheckTests(unittest.TestCase):
    def write(self, root, rel, body, *, lang="en", canonical=None, extra_head="", links=""):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        canonical = canonical or f"https://titoneedsakidney.com/{rel.as_posix()}"
        path.write_text(
            f'<!doctype html><html lang="{lang}"><head><title>Example</title>'
            f'<link rel="canonical" href="{canonical}">{extra_head}</head><body>'
            f'<a class="skip-link" href="#main">Skip</a><main id="main">{body}{links}</main>'
            '</body></html>', encoding="utf-8"
        )
        return path

    def test_detects_duplicate_ids_and_landmarks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(root, Path("page.html"), '<h1>One</h1><div id="x"></div><div id="x"></div><main></main>')
            parser = integrity.parse_page(page)
            self.assertIn("duplicate id values: x", integrity.check_page(root, Path("page.html"), {Path("page.html")}))
            self.assertIn("expected exactly one main landmark, found 2", integrity.check_page(root, Path("page.html"), {Path("page.html")}))

    def test_detects_bad_skip_target_and_runtime_include(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(root, Path("page.html"), '<h1>One</h1><div data-include="/includes/header.html"></div>')
            text = page.read_text(encoding="utf-8").replace('href="#main"', 'href="#missing"')
            page.write_text(text, encoding="utf-8")
            errors = integrity.check_page(root, Path("page.html"), {Path("page.html")})
            self.assertTrue(any("skip-link target" in error for error in errors))
            self.assertIn("runtime data-include placeholder remains", errors)

    def test_detects_forbidden_draft_text(self):
        self.assertEqual(
            ["forbidden draft text remains: \"I'm going one by one\""],
            integrity.check_forbidden_draft_text("I'm going one by one <nav>"),
        )

    def test_detects_broken_links_and_fragments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, Path("page.html"), '<h1>One</h1>', links='<a href="/missing.html">Missing</a><a href="#missing">Fragment</a>')
            errors = integrity.check_links(root, [Path("page.html")])
            self.assertEqual(2, len(errors))

    def test_detects_duplicate_index_links_but_allows_external_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(
                root,
                Path("page.html"),
                '<h1>One</h1>',
                links=(
                    '<a href="/hub/index.html">Duplicate</a>'
                    '<a href="https://titoneedsakidney.com/es/index.html">Duplicate absolute</a>'
                    '<a href="https://example.com/index.html">External</a>'
                ),
            )
            self.assertEqual(
                [
                    "internal links use duplicate index.html URLs: "
                    "/hub/index.html, https://titoneedsakidney.com/es/index.html"
                ],
                integrity.check_duplicate_url_links(integrity.parse_page(page)),
            )

    def test_detects_duplicate_visible_bodies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, Path("one.html"), '<h1>One</h1><p>Same body</p>')
            self.write(root, Path("two.html"), '<h1>Two</h1><p>Same body</p>')
            self.assertEqual([], integrity.check_duplicate_bodies(root, [Path("one.html"), Path("two.html")]))
            self.write(root, Path("two.html"), '<h1>One</h1><p>Same body</p>')
            self.assertEqual(1, len(integrity.check_duplicate_bodies(root, [Path("one.html"), Path("two.html")])))

    def test_detects_invalid_json_ld(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(root, Path("page.html"), '<h1>One</h1>', extra_head='<script type="application/ld+json">{bad}</script>')
            errors = integrity.check_json_ld(Path("page.html"), integrity.parse_page(page))
            self.assertTrue(any("invalid JSON-LD" in error for error in errors))

    def test_detects_language_canonical_alternates_and_role_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(
                root, Path("page.html"), '<h1>Nephrologist</h1>', lang="es",
                canonical="https://titoneedsakidney.com/wrong.html",
                extra_head='<meta property="og:title" content="Social Worker">',
            )
            errors = integrity.check_page(root, Path("page.html"), {Path("page.html")})
            self.assertTrue(any(error.startswith("lang is") for error in errors))
            self.assertTrue(any(error.startswith("canonical is") for error in errors))
            self.assertIn("hreflang alternates do not match the bilingual counterpart", errors)
            self.assertIn("role named by title/metadata conflicts with H1 content", errors)

    def test_detects_english_hub_navigation_on_spanish_pages_but_allows_language_switch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = self.write(
                root, Path("es/page.html"),
                '<h1>Uno</h1><nav><a href="/hub/dialysis/">English hub</a></nav>',
                lang="es",
            )
            errors = integrity.check_spanish_navigation_links(
                Path("es/page.html"), integrity.parse_page(page)
            )
            self.assertEqual(
                ["Spanish navigation links to English /hub/ routes: /hub/dialysis/"],
                errors,
            )

            page = self.write(
                root, Path("es/page.html"),
                '<h1>Uno</h1><nav><div class="lang-switch">'
                '<a href="/hub/dialysis/">EN</a></div></nav>',
                lang="es",
            )
            self.assertEqual(
                [],
                integrity.check_spanish_navigation_links(
                    Path("es/page.html"), integrity.parse_page(page)
                ),
            )

    def test_detects_sitemap_membership_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, Path("page.html"), '<h1>One</h1>')
            ElementTree.ElementTree(ElementTree.Element("urlset")).write(
                root / "sitemap.xml", encoding="utf-8", xml_declaration=True
            )
            self.assertEqual(
                ["sitemap membership does not match canonical standalone pages"],
                integrity.check_sitemap(root, [Path("page.html")]),
            )


if __name__ == "__main__":
    unittest.main()
