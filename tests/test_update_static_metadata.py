import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_static_metadata as metadata


def page(title, body, managed_description, og_title, og_description):
    return f'''<!doctype html>
<html lang="en"><head><title>{title}</title>
<!-- STATIC SEO METADATA: BEGIN -->
<meta name="description" content="{managed_description}">
<meta property="og:type" content="website">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_description}">
<!-- STATIC SEO METADATA: END -->
</head><body><main id="main"><h1>{title}</h1><p>{body}</p></main></body></html>'''


class StaticMetadataTests(unittest.TestCase):
    def write_and_process(self, rel, content):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        metadata.process_page(root, rel, {rel}, apply=True)
        return temp, path.read_text(encoding="utf-8")

    def test_preserves_curated_managed_social_metadata(self):
        temp, rendered = self.write_and_process(
            Path("book.html"),
            page("Generic page title", "A deliberately generic page summary." * 4,
                 "Curated page description", "Curated Open Graph title",
                 "Curated Open Graph description"),
        )
        self.addCleanup(temp.cleanup)
        self.assertIn('content="Curated page description"', rendered)
        self.assertIn('content="Curated Open Graph title"', rendered)
        self.assertIn('content="Curated Open Graph description"', rendered)

    def test_refresh_allowlist_rebuilds_corrected_social_worker_metadata(self):
        rel = Path("es/hub/transplant/preop/staff/social-worker.html")
        temp, rendered = self.write_and_process(
            rel,
            page("Trabajador/a social de trasplante",
                 "El trabajador social ayuda con apoyo, recursos y planificación práctica." * 3,
                 "Antigua descripción de nefrología", "Título antiguo",
                 "Antigua descripción de nefrología"),
        )
        self.addCleanup(temp.cleanup)
        self.assertNotIn("Antigua descripción de nefrología", rendered)
        self.assertIn('property="og:title" content="Trabajador/a social de trasplante"', rendered)
        self.assertIn("El trabajador social ayuda", rendered)


if __name__ == "__main__":
    unittest.main()
