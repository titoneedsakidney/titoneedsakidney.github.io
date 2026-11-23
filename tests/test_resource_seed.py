"""Source-inventory guard for site-kidney-directory-s1. No live URL claims are inferred."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_resource_data import validate, publishable

class ResourceSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/kidney-resource-placements.json").read_text())

    def test_schema(self):
        self.assertEqual([], validate(self.data))

    def test_all_original_needs_and_new_candidates_preserved(self):
        self.assertEqual(25, len(self.data["placements"]))
        self.assertEqual(10, len(self.data["organizations"]))
        ids = {p["placement_id"] for p in self.data["placements"]}
        self.assertTrue({"kidneytexas-candidate", "pkdfree-candidate", "nkf-serving-texas"} <= ids)

    def test_only_current_official_source_checked_entries_released(self):
        expected = {"nkf-peers-en", "akf-safety-net", "akf-community-finder", "igan-support"}
        self.assertEqual(expected, {p["placement_id"] for p in publishable(self.data)})
        self.assertTrue(all(p["verified_at"] == "2026-11-23" for p in publishable(self.data)))

    def test_historical_and_candidate_entries_fail_closed(self):
        self.assertTrue(all(p["status"] == "excluded" for p in self.data["placements"]
                            if p["verified_at"] == "2026-09-02"))
        self.assertTrue(all(p["status"] == "excluded" for p in self.data["placements"]
                            if p["placement_id"] in {"kidneytexas-candidate", "pkdfree-candidate", "nkf-serving-texas"}))

if __name__ == "__main__":
    unittest.main()
