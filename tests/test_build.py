from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hometv.build import (
    BuildError,
    MirrorRequest,
    build_cn,
    build_curated_vod,
    build_us,
    mirror_files,
)
from hometv.curation import CuratedSource


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
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)

    def tearDown(self):
        self._temporary_directory.cleanup()

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
            },
        )

    def test_cn_build_omits_confirmed_dead_live_lists(self):
        result = build_cn(fixture(), GITEE_BASE)
        names = [live["name"] for live in result.config["lives"]]
        self.assertEqual(names, ["Kimentanm"])

    def test_us_build_omits_confirmed_dead_live_lists(self):
        result = build_us(fixture())
        names = [live["name"] for live in result["lives"]]
        self.assertEqual(names, ["Kimentanm"])

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

    def test_curated_build_keeps_nitan_global_and_isolates_wanger(self):
        policy = CuratedSource("wangerxiao", "🐮", ("wang",))
        nitan = {"spider": "https://nitan/spider.png", "sites": [{"key": "nitan", "name": "泥潭"}], "lives": []}
        wanger = {"spider": "https://upstream/spider.jpg;md5;0123456789abcdef0123456789abcdef", "sites": [
            {"key": "wang", "name": "王", "type": 3, "api": "csp_Wang", "ext": {"keep": True}}
        ]}
        us = build_curated_vod(nitan, wanger, policy, "us", "https://raw.githubusercontent.com/o/r/main", "https://gitee.com/o/r/raw/main")
        cn = build_curated_vod(nitan, wanger, policy, "cn", "https://raw.githubusercontent.com/o/r/main", "https://gitee.com/o/r/raw/main")
        self.assertEqual(us.config["spider"], nitan["spider"])
        self.assertEqual(us.config["sites"][1]["jar"], "https://raw.githubusercontent.com/o/r/main/vendor/wanger/spider.jpg;md5;0123456789abcdef0123456789abcdef")
        self.assertEqual(cn.config["sites"][1]["jar"], "https://gitee.com/o/r/raw/main/vendor/wanger/spider.jpg;md5;0123456789abcdef0123456789abcdef")
        self.assertEqual(cn.config["sites"][1]["ext"], {"keep": True})
        self.assertEqual([item.repository_path for item in us.mirrors], ["vendor/wanger/spider.jpg"])

    @patch("urllib.request.urlopen")
    def test_wanger_mirror_rejects_md5_mismatch_and_keeps_previous(self, urlopen):
        destination = self.root / "vendor/wanger/spider.jpg"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"known-good")
        urlopen.return_value = FakeResponse(b"wrong", "image/jpeg")
        request = MirrorRequest("https://upstream/spider.jpg", "vendor/wanger/spider.jpg", "0123456789abcdef0123456789abcdef")
        with self.assertRaisesRegex(BuildError, "MD5 mismatch"):
            mirror_files((request,), self.root)
        self.assertEqual(destination.read_bytes(), b"known-good")

    @patch("urllib.request.urlopen")
    def test_wanger_mirror_records_expected_and_actual_md5(self, urlopen):
        urlopen.return_value = FakeResponse(b"verified", "image/jpeg")
        request = MirrorRequest(
            "https://upstream/spider.jpg",
            "vendor/wanger/spider.jpg",
            "723aa82a83c278d5e7e7be9b109b406a",
        )
        manifest = mirror_files((request,), self.root)
        self.assertEqual(
            manifest["files"][0].get("expected_md5"),
            "723aa82a83c278d5e7e7be9b109b406a",
        )
        self.assertEqual(
            manifest["files"][0].get("md5"), "723aa82a83c278d5e7e7be9b109b406a"
        )


if __name__ == "__main__":
    unittest.main()
