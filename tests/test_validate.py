import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from hometv.validate import (
    ProbeResult,
    probe_http,
    validate_config,
    validate_live_config,
    write_health_report,
)


class FakeHeaders:
    def __init__(self, content_type):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    status = 200

    def __init__(self, body, content_type):
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        return self.body


class ValidateTests(unittest.TestCase):
    def test_reports_shapes_duplicate_keys_and_cleartext(self):
        config = {
            "spider": "https://example.com/spider.jar",
            "sites": [
                {"key": "same", "api": "http://example.com/api"},
                {"key": "same", "api": "https://example.com/api2"},
            ],
            "lives": "not-a-list",
        }
        findings = validate_config(config, "us")
        messages = [(item.severity, item.code) for item in findings]
        self.assertIn(("error", "duplicate-site-key"), messages)
        self.assertIn(("error", "invalid-lives"), messages)
        self.assertIn(("warning", "cleartext-http"), messages)

    def test_mainland_rejects_github_dependencies(self):
        config = {
            "spider": "https://raw.githubusercontent.com/example/repo/main/spider.jar",
            "sites": [],
            "lives": [],
        }
        findings = validate_config(config, "cn")
        self.assertIn("mainland-github-url", {item.code for item in findings if item.severity == "error"})

    def test_live_validation_accepts_a_complete_live_config(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "https://example.com/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                }
            ]
        }
        self.assertEqual(validate_live_config(config, "us"), [])

    def test_live_validation_requires_unique_names_urls_and_one_boot(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "https://example.com/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                },
                {
                    "name": "A",
                    "url": "https://example.com/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                },
            ]
        }
        codes = {finding.code for finding in validate_live_config(config, "us")}
        self.assertIn("duplicate-live-name", codes)
        self.assertIn("duplicate-live-url", codes)
        self.assertIn("invalid-live-boot-count", codes)

    def test_live_validation_requires_non_empty_valid_entries(self):
        config = {
            "lives": [
                {
                    "name": "",
                    "url": "ftp://example.com/a.m3u",
                    "boot": False,
                    "ua": "",
                    "timeout": 0,
                }
            ]
        }
        codes = {finding.code for finding in validate_live_config(config, "us")}
        self.assertIn("invalid-live-name", codes)
        self.assertIn("invalid-live-url", codes)
        self.assertIn("invalid-live-ua", codes)
        self.assertIn("invalid-live-timeout", codes)
        self.assertIn("invalid-live-boot-count", codes)

    def test_live_validation_rejects_empty_or_non_object_config(self):
        self.assertIn(
            "invalid-live-config",
            {finding.code for finding in validate_live_config([], "us")},
        )
        self.assertIn(
            "invalid-lives",
            {finding.code for finding in validate_live_config({"lives": []}, "us")},
        )

    def test_live_validation_applies_mainland_github_and_cleartext_rules(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "https://raw.githubusercontent.com/example/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                    "epg": "http://example.com/epg.xml",
                }
            ]
        }
        findings = validate_live_config(config, "cn")
        codes = {(item.severity, item.code) for item in findings}
        self.assertIn(("error", "mainland-github-url"), codes)
        self.assertIn(("warning", "cleartext-http"), codes)

    def test_live_validation_rejects_unknown_region(self):
        self.assertIn(
            "invalid-region",
            {finding.code for finding in validate_live_config({"lives": []}, "eu")},
        )

    def test_live_validation_marks_malformed_http_url_invalid_without_raising(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "https://[bad",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                }
            ]
        }
        codes = {finding.code for finding in validate_live_config(config, "us")}
        self.assertIn("invalid-live-url", codes)

    def test_live_validation_ignores_malformed_recursive_url_without_raising(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "https://example.com/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                    "epg": "https://[bad",
                }
            ]
        }
        self.assertEqual(validate_live_config(config, "us"), [])

    def test_live_validation_recognizes_uppercase_http_schemes(self):
        config = {
            "lives": [
                {
                    "name": "A",
                    "url": "HTTPS://raw.githubusercontent.com/example/a.m3u",
                    "boot": True,
                    "ua": "okhttp/4.12.0",
                    "timeout": 15,
                    "epg": "HTTP://example.com/epg.xml",
                }
            ]
        }
        codes = {
            (finding.severity, finding.code)
            for finding in validate_live_config(config, "cn")
        }
        self.assertIn(("error", "mainland-github-url"), codes)
        self.assertIn(("warning", "cleartext-http"), codes)

    @patch("urllib.request.urlopen")
    def test_probe_rejects_html_error_page_with_200_status(self, urlopen):
        urlopen.return_value = FakeResponse(b"<html>blocked</html>", "text/html")
        result = probe_http("https://example.com/config.json?token=secret")
        self.assertFalse(result.ok)
        self.assertEqual(result.target, "https://example.com/config.json")
        self.assertIn("HTML", result.error)

    @patch("urllib.request.urlopen")
    def test_playlist_probe_fetches_first_media_resource(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(b"#EXTM3U\n#EXTINF:10,one\nsegment.ts\n", "application/vnd.apple.mpegurl"),
            FakeResponse(b"media-bytes", "video/mp2t"),
        ]
        result = probe_http("https://example.com/live/stream.m3u8")
        self.assertTrue(result.ok)
        self.assertEqual(result.media_target, "https://example.com/live/segment.ts")
        self.assertEqual(result.bytes, 11)

    @patch("urllib.request.urlopen")
    def test_playlist_probe_skips_dead_channels_until_one_works(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(
                b"#EXTM3U\n#EXTINF:-1,dead\nhttps://example.com/dead.ts\n"
                b"#EXTINF:-1,good\nhttps://example.com/good.ts\n",
                "application/vnd.apple.mpegurl",
            ),
            urllib.error.HTTPError(
                "https://example.com/dead.ts", 404, "not found", None, None
            ),
            FakeResponse(b"working-media", "video/mp2t"),
        ]
        result = probe_http("https://example.com/live/list.m3u")
        self.assertTrue(result.ok)
        self.assertEqual(result.media_target, "https://example.com/good.ts")

    @patch("urllib.request.urlopen")
    def test_probe_uses_okhttp_user_agent_for_catvod_apis(self, urlopen):
        def respond(request, timeout):
            if request.headers.get("User-agent") == "okhttp/4.12.0":
                return FakeResponse(b'{"class":[]}', "application/json")
            return FakeResponse(b"<html>challenge</html>", "text/html")

        urlopen.side_effect = respond
        result = probe_http("https://vod.catvod.ggff.net/guazi")
        self.assertTrue(result.ok)

    @patch("urllib.request.urlopen")
    def test_probe_accepts_spider_assets_up_to_four_mib(self, urlopen):
        urlopen.return_value = FakeResponse(b"x" * (3 * 1024 * 1024), "application/octet-stream")
        result = probe_http("https://example.com/spider.jar")
        self.assertTrue(result.ok)

    def test_health_report_marks_probe_failures_and_hides_queries(self):
        probe = ProbeResult(
            target="https://example.com/api",
            ok=False,
            status_code=503,
            elapsed_ms=12,
            bytes=0,
            sha256="",
            content_type="text/plain",
            error="unavailable",
            media_target="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "health.json"
            write_health_report("cn", [], [probe], path, "github-actions-us-approximation")
            report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["probe_origin"], "github-actions-us-approximation")


if __name__ == "__main__":
    unittest.main()
