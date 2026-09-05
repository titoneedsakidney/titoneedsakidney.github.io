import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "outreach-landing-paths.json"
ORIGIN = "https://titoneedsakidney.com"
CAMPAIGN_QUERY = {
    "utm_source": "organization-outreach",
    "utm_medium": "email",
    "utm_campaign": "cmp-02",
    "utm_content": "first-contact-resource-en-v1",
}


def page_for_path(path: str) -> Path:
    relative = path.lstrip("/")
    if not relative or path.endswith("/"):
        return ROOT / relative / "index.html"
    return ROOT / relative


class OutreachLandingPathsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.roles = cls.contract["roles"]

    def test_contract_uses_only_clean_stable_site_paths(self):
        self.assertEqual(self.contract["canonical_origin"], ORIGIN)
        self.assertEqual(self.contract["schema_id"], "tnk-outreach-landing-paths-v1")

        for role, path in self.roles.items():
            with self.subTest(role=role):
                parsed = urlsplit(path)
                self.assertEqual(parsed.scheme, "")
                self.assertEqual(parsed.netloc, "")
                self.assertEqual(parsed.query, "")
                self.assertEqual(parsed.fragment, "")
                self.assertTrue(path.startswith("/"))
                self.assertTrue(page_for_path(path).is_file(), path)

    def test_bilingual_roles_point_to_reciprocal_clean_canonicals(self):
        for role, path in self.roles.items():
            if not role.endswith("_en"):
                continue
            spanish_role = f"{role[:-3]}_es"
            self.assertIn(spanish_role, self.roles)
            spanish_path = self.roles[spanish_role]

            english_html = page_for_path(path).read_text(encoding="utf-8")
            spanish_html = page_for_path(spanish_path).read_text(encoding="utf-8")
            english_canonical = f'<link rel="canonical" href="{ORIGIN}{path}">'
            spanish_canonical = f'<link rel="canonical" href="{ORIGIN}{spanish_path}">'

            with self.subTest(role=role, language="en"):
                self.assertIn(english_canonical, english_html)
                self.assertIn(
                    f'<link rel="alternate" hreflang="es" href="{ORIGIN}{spanish_path}">',
                    english_html,
                )
            with self.subTest(role=spanish_role, language="es"):
                self.assertIn(spanish_canonical, spanish_html)
                self.assertIn(
                    f'<link rel="alternate" hreflang="en" href="{ORIGIN}{path}">',
                    spanish_html,
                )

    def test_representative_campaign_urls_keep_the_clean_page_contract(self):
        for role, path in self.roles.items():
            query = CAMPAIGN_QUERY | {
                "utm_content": f"first-contact-{role.replace('_', '-')}-v1"
            }
            query_text = "&".join(f"{key}={value}" for key, value in query.items())
            parsed = urlsplit(f"{ORIGIN}{path}?{query_text}")
            with self.subTest(role=role):
                self.assertEqual(parsed.scheme, "https")
                self.assertEqual(parsed.netloc, "titoneedsakidney.com")
                self.assertEqual(parsed.path, path)
                self.assertEqual(dict(parse_qsl(parsed.query)), query)
                self.assertTrue(page_for_path(parsed.path).is_file())

    def test_internal_links_do_not_propagate_campaign_queries(self):
        for html_path in ROOT.rglob("*.html"):
            html = html_path.read_text(encoding="utf-8")
            with self.subTest(page=html_path.relative_to(ROOT)):
                self.assertIsNone(re.search(r'href=["\'][^"\']*\butm_[^"\']*["\']', html))


if __name__ == "__main__":
    unittest.main()
