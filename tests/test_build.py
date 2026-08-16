from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hometv.build import BuildError, build_cn, build_us, mirror_files


GITEE_BASE = "https://gitee.com/ds4213tv/hometv/raw/main"


def fixture():
    return {
        "spider": "https://github.com/nitan-tv/nitan/raw/refs/heads/main/awdm.png",
        "wallpaper": "https://example.com/wallpaper",
        "sites": [
            {
                "key": "Douban",
                "api": "csp_DoubanAmns",
                "ext": "https://github.com/nitan-tv/nitan/raw/refs/heads/main/db.aowu",
            },
            {
                "key": "Jinpai",
                "api": "https://github.com/nitan-tv/nitan/raw/refs/heads/main/py/py_jinpai.py",
            },
        ],
        "lives": [
            {
                "name": "Kimentanm",
                "url": "https://raw.githubusercontent.com/Kimentanm/aptv/refs/heads/master/m3u/iptv.m3u",
            },
            {
                "name": "Migu",
                "url": "https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt",
            },
            {
                "name": "YanG",
                "url": "https://iptv.yang-1989.eu.org/m3u/Gather.m3u",
            },
            {
                "name": "YanG Sport",
                "url": "https://iptv.yang-1989.eu.org/m3u/Sport.m3u",
            },
        ],
        "doh": [{"name": "Google", "url": "https://dns.google/dns-query"}],
    }


class FakeHeaders:
    def __init__(self, content_type):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    status = 200

    def __init__(self, body=b"asset", content_type="application/octet-stream"):
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        return self.body


class BuildTests(unittest.TestCase):
    def test_us_build_is_an_independent_copy(self):
        original = fixture()
        result = build_us(original)
        result["sites"][0]["key"] = "changed"
        self.assertEqual(original["sites"][0]["key"], "Douban")

    def test_cn_build_rewrites_static_dependencies(self):
        original = fixture()
        unchanged = deepcopy(original)
        result = build_cn(original, GITEE_BASE)

        self.assertEqual(result.config["spider"], f"{GITEE_BASE}/vendor/nitan/awdm.png")
        self.assertEqual(result.config["sites"][0]["ext"], f"{GITEE_BASE}/vendor/nitan/db.aowu")
        self.assertEqual(
            result.config["sites"][1]["api"],
            f"{GITEE_BASE}/vendor/nitan/py/py_jinpai.py",
        )
        serialized = json.dumps(result.config)
        self.assertNotIn("raw.githubusercontent.com", serialized)
        self.assertNotIn("github.com", serialized)
        self.assertEqual([item["name"] for item in result.config["doh"]], ["AliDNS", "DNSPod"])
        self.assertEqual(result.config["wallpaper"], "")
        self.assertEqual(original, unchanged)

    def test_cn_build_requests_every_rewritten_asset(self):
        result = build_cn(fixture(), GITEE_BASE)
        paths = {request.repository_path for request in result.mirrors}
        self.assertEqual(
            paths,
            {
                "vendor/nitan/awdm.png",
                "vendor/nitan/db.aowu",
                "vendor/nitan/py/py_jinpai.py",
                "vendor/live/kimentanm.m3u",
                "vendor/live/migu.txt",
            },
        )

    def test_cn_build_omits_confirmed_dead_live_lists(self):
        result = build_cn(fixture(), GITEE_BASE)
        names = [live["name"] for live in result.config["lives"]]
        self.assertEqual(names, ["Kimentanm", "Migu"])

    @patch("urllib.request.urlopen")
    def test_mirror_files_writes_assets_and_manifest(self, urlopen):
        urlopen.return_value = FakeResponse(b"asset-data")
        requests = build_cn(fixture(), GITEE_BASE).mirrors[:1]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = mirror_files(requests, Path(temp_dir))
            path = Path(temp_dir) / requests[0].repository_path
            self.assertEqual(path.read_bytes(), b"asset-data")
            self.assertEqual(manifest["files"][0]["bytes"], 10)
            self.assertEqual(manifest["files"][0]["path"], requests[0].repository_path)

    @patch("urllib.request.urlopen")
    def test_html_mirror_failure_keeps_previous_asset(self, urlopen):
        urlopen.return_value = FakeResponse(b"<html>blocked</html>", "text/html")
        request = build_cn(fixture(), GITEE_BASE).mirrors[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / request.repository_path
            path.parent.mkdir(parents=True)
            path.write_bytes(b"known-good")
            with self.assertRaisesRegex(BuildError, "HTML"):
                mirror_files((request,), root)
            self.assertEqual(path.read_bytes(), b"known-good")


if __name__ == "__main__":
    unittest.main()
