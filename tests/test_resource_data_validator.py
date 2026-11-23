"""Synthetic, offline regression tests for the public directory data gate."""
import copy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_resource_data.py"
spec = importlib.util.spec_from_file_location("check_resource_data", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample():
    return {
        "schema": "kidney-resource-placements-v1",
        "organizations": [
            {"organization_id": "example-a", "name": "Example A", "official_url": "https://example.org/"}
        ],
        "placements": [
            {"placement_id": "help-one", "organization_id": "example-a",
             "need": "transportation", "destination_url": "https://example.org/ride",
             "destination_language": "en", "geography": "United States",
             "verified_at": "2026-09-02", "source_url": "https://example.org/ride",
             "status": "verified"},
            {"placement_id": "help-two", "organization_id": "example-a",
             "need": "insurance", "destination_url": "https://example.org/insurance",
             "destination_language": "es", "geography": "United States",
             "verified_at": "2026-09-02", "source_url": "https://example.org/insurance",
             "status": "excluded"}
        ]
    }


class ResourceDataTests(unittest.TestCase):
    def test_valid_one_organization_multiple_placements(self):
        self.assertEqual(module.validate(sample()), [])
        self.assertEqual([p["placement_id"] for p in module.publishable(sample())], ["help-one"])

    def test_duplicate_placement_and_organization(self):
        data = sample()
        data["placements"].append(copy.deepcopy(data["placements"][0]))
        data["organizations"].append(copy.deepcopy(data["organizations"][0]))
        errors = module.validate(data)
        self.assertTrue(any("duplicate placement_id" in e for e in errors))
        self.assertTrue(any("duplicate organization_id" in e for e in errors))

    def test_reject_unknown_organization(self):
        data = sample()
        data["placements"][0]["organization_id"] = "missing-org"
        self.assertTrue(any("unknown organization_id" in e for e in module.validate(data)))

    def test_reject_missing_or_future_verification(self):
        for value in (None, "", "2026-02-30", "2999-01-01", "yesterday"):
            with self.subTest(value=value):
                data = sample()
                data["placements"][0]["verified_at"] = value
                self.assertTrue(module.validate(data))

    def test_reject_bad_language_and_geography(self):
        for field, value in (("destination_language", "fr"), ("geography", "")):
            with self.subTest(field=field):
                data = sample()
                data["placements"][0][field] = value
                self.assertTrue(module.validate(data))

    def test_reject_nonofficial_or_unusable_url_shape(self):
        for value in ("http://example.org/", "javascript:alert(1)", "https://user:pw@example.org/",
                      "https://example.org/#fragment", "https://bad url.org/"):
            with self.subTest(value=value):
                data = sample()
                data["placements"][0]["source_url"] = value
                self.assertTrue(module.validate(data))

    def test_reject_private_fields_even_nested(self):
        for field in ("contact_email", "crm_id", "private_notes", "endorsement"):
            with self.subTest(field=field):
                data = sample()
                data["placements"][0][field] = "secret"
                self.assertTrue(any("private or unsupported claim field" in e for e in module.validate(data)))

    def test_reject_unsubstantiated_claims(self):
        data = sample()
        data["organizations"][0]["name"] = "Official partner of Example Foundation"
        self.assertTrue(any("unsupported name" in e for e in module.validate(data)))

    def test_excluded_rows_cannot_publish(self):
        data = sample()
        data["placements"][0]["status"] = "excluded"
        self.assertEqual(module.publishable(data), [])

    def test_fail_closed_for_malformed_root(self):
        self.assertTrue(module.validate([]))
        self.assertTrue(module.validate({"schema": "wrong", "organizations": [], "placements": []}))
        with self.assertRaises(ValueError):
            module.publishable({"schema": "wrong", "organizations": [], "placements": []})


if __name__ == "__main__":
    unittest.main()
