from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hometv.curation import CurationError
from hometv.us_vod import extend_us_vod


class USVodTests(unittest.TestCase):
    def test_missing_policy_preserves_existing_config(self):
        base = {"spider": "https://old/jar", "sites": [{"key": "old"}], "lives": [{"url": "https://live/list"}]}
        with tempfile.TemporaryDirectory() as directory:
            result = extend_us_vod(Path(directory), base, "https://delivery")
            self.assertEqual(result, base)
            self.assertIsNot(result, base)

    def test_verified_extension_preserves_fallback_dependencies_and_live_config(self):
        base = {"spider": "https://old/jar", "sites": [{"key": "old", "quickSearch": 1}], "lives": [{"url": "https://live/list"}]}
        original = deepcopy(base)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b"verified-plugin"
            digest = hashlib.md5(raw).hexdigest()
            settings = {"schema": 1, "source_id": "qist-fty", "name_prefix": "饭太硬·", "keys": ["sample"], "quick_search_keys": ["sample"], "commit": "pinned", "spider_md5": digest}
            candidate = {"spider": "./jar/fan.txt;md5;" + digest, "sites": [{"key": "sample", "name": "sample", "type": 3, "api": "csp_Sample", "ext": {"Cloud-drive": "private-path", "siteUrl": "https://video"}}]}
            for relative, content in (("sources/us-vod.json", settings), ("candidates/qist-fty/upstream.json", candidate)):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(content), encoding="utf-8")
            jar = root / f"vendor/qist/fan-{digest}.txt"
            jar.parent.mkdir(parents=True)
            jar.write_bytes(raw)
            result = extend_us_vod(root, base, "https://delivery")
            self.assertEqual(result["lives"], original["lives"])
            self.assertEqual(base, original)
            self.assertEqual(result["sites"][1]["jar"], original["spider"])
            self.assertEqual(result["sites"][0]["ext"], {"siteUrl": "https://video"})
            self.assertTrue(result["spider"].endswith(";md5;" + digest))
            jar.write_bytes(b"corrupt")
            with self.assertRaisesRegex(CurationError, "MD5 mismatch"):
                extend_us_vod(root, base, "https://delivery")
