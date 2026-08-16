from pathlib import Path
import json
import tempfile
import unittest

from hometv.registry import RegistryError, load_registry


class RegistryTests(unittest.TestCase):
    def test_loads_nitan_as_initial_stable_source(self):
        sources = load_registry(Path("sources/registry.json"))
        nitan = next(source for source in sources if source.id == "nitan-dm")
        self.assertEqual(nitan.regions, ("us", "cn"))
        self.assertEqual(nitan.stable_regions, ("us", "cn"))

    def test_dead_sources_are_disabled_with_reasons(self):
        sources = load_registry(Path("sources/registry.json"))
        aowu = next(source for source in sources if source.id == "aowu")
        self.assertFalse(aowu.enabled)
        self.assertIn("404", aowu.disabled_reason)

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
