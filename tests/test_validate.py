import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hometv.validate import ProbeResult, probe_http, validate_config, write_health_report


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
