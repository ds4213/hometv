import unittest
from pathlib import Path

from hometv.curation import (
    CurationError,
    CuratedSource,
    load_curated_source,
    merge_curated_sites,
    select_curated_sites,
)


class CurationTests(unittest.TestCase):
    def test_real_policy_contains_exact_approved_keys(self):
        policy = load_curated_source(Path("sources/wanger-curated.json"))
        self.assertEqual(policy.source_id, "wangerxiao")
        self.assertEqual(policy.name_prefix, "🐮")
        self.assertEqual(len(policy.keys), 35)
        self.assertEqual(len(set(policy.keys)), 35)

    def test_selection_preserves_upstream_order_and_fields(self):
        policy = CuratedSource("wangerxiao", "🐮", ("b", "a"))
        upstream = {"sites": [
            {"key": "a", "name": "A", "type": 3, "api": "csp_A", "ext": {"x": 1}},
            {"key": "ignored", "name": "I", "type": 3, "api": "csp_I"},
            {"key": "b", "name": "B", "type": 3, "api": "csp_B", "timeout": 120},
        ]}
        selected = select_curated_sites(upstream, policy, "https://repo/spider.jpg;md5;abc")
        self.assertEqual([site["key"] for site in selected], ["a", "b"])
        self.assertEqual(selected[0]["ext"], {"x": 1})
        self.assertEqual(selected[1]["timeout"], 120)
        self.assertTrue(all(site["name"].startswith("🐮") for site in selected))
        self.assertTrue(all(site["jar"].endswith(";md5;abc") for site in selected))

    def test_missing_duplicate_or_base_collision_is_rejected(self):
        policy = CuratedSource("wangerxiao", "🐮", ("a", "b"))
        with self.assertRaisesRegex(CurationError, "missing curated keys: b"):
            select_curated_sites({"sites": [{"key": "a", "name": "A", "type": 3}]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "duplicate upstream key: a"):
            select_curated_sites({"sites": [
                {"key": "a", "name": "A", "type": 3},
                {"key": "a", "name": "A2", "type": 3},
                {"key": "b", "name": "B", "type": 3},
            ]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "site key collision: a"):
            merge_curated_sites({"spider": "nitan", "sites": [{"key": "a"}]}, [{"key": "a"}])


if __name__ == "__main__":
    unittest.main()
