import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_pages_artifact.py"
spec = importlib.util.spec_from_file_location("pages_artifact", MODULE_PATH)
pages_artifact = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pages_artifact)


class HostedPagesCdTests(unittest.TestCase):
    def test_workflow_is_hosted_and_requires_successful_main_validation(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("self-hosted", workflow)
        self.assertIn("workflow_run", workflow)
        self.assertIn("head_branch == 'main'", workflow)
        self.assertIn("conclusion == 'success'", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)

    def test_workflow_never_deploys_from_pull_request(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("DISPATCH_REF", workflow)
        self.assertIn("refs/heads/main", workflow)

    def test_builder_excludes_repository_machinery_and_noindex(self):
        self.assertIn(".github", pages_artifact.SKIP_DIRS)
        self.assertIn("scripts", pages_artifact.SKIP_DIRS)
        self.assertIn("tests", pages_artifact.SKIP_DIRS)
        self.assertIn("docs", pages_artifact.SKIP_DIRS)
        prototype = ROOT / "includes" / "prototypes" / "issue-19" / "index.html"
        if prototype.exists():
            self.assertFalse(pages_artifact.is_deployable_html(prototype))

    def test_builder_produces_required_site_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            result = pages_artifact.build(output)
            self.assertGreater(result["pages"], 0)
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "CNAME").is_file())
            self.assertTrue((output / "assets").is_dir())
            self.assertFalse((output / ".github").exists())
            self.assertFalse((output / "tests").exists())
            self.assertFalse((output / "scripts").exists())


if __name__ == "__main__":
    unittest.main()
