from pathlib import Path
import json
import tempfile
import unittest

from hometv.registry import RegistryError, load_registry


class RegistryTests(unittest.TestCase):
    def test_production_registry_enables_exact_five_sources_for_both_regions(self):
        sources = load_registry(Path("sources/registry.json"))
        self.assertEqual(
            [source.id for source in sources],
            ["nitan-dm", "wangerxiao", "aowu", "fantaiying", "ok"],
        )
        self.assertTrue(all(source.enabled for source in sources))
        self.assertTrue(all(source.regions == ("us", "cn") for source in sources))
        stable = {source.id: source.stable_regions for source in sources}
        self.assertEqual(stable["nitan-dm"], ("us", "cn"))
        self.assertEqual(stable["wangerxiao"], ("us", "cn"))
        self.assertEqual(stable["aowu"], ())
        self.assertEqual(stable["fantaiying"], ())
        self.assertEqual(stable["ok"], ())

    def test_rejects_duplicate_ids(self):
        payload = {
            "schema": 1,
            "sources": [
                {
                    "id": "same",
                    "name": "one",
                    "url": "https://example.com/one.json",
                    "regions": ["us"],
                    "enabled": True,
                    "stable_regions": [],
                },
                {
                    "id": "same",
                    "name": "two",
                    "url": "https://example.com/two.json",
                    "regions": ["cn"],
                    "enabled": True,
                    "stable_regions": [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RegistryError, "duplicate source id"):
                load_registry(path)

    def test_disabled_source_requires_reason(self):
        payload = {
            "schema": 1,
            "sources": [
                {
                    "id": "disabled",
                    "name": "disabled",
                    "url": "https://example.com/config.json",
                    "regions": ["cn"],
                    "enabled": False,
                    "stable_regions": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RegistryError, "disabled_reason"):
                load_registry(path)


if __name__ == "__main__":
    unittest.main()
