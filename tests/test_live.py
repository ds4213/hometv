import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from hometv.live import (
    M3UEntry,
    PlaylistError,
    fetch_live_bytes,
    merge_playlists,
    parse_m3u,
    publish_playlist,
    serialize_m3u,
    validate_playlist,
)


def make_playlist(count: int, include_cctv: bool, include_satellite: bool) -> bytes:
    names = [f"频道{index:02d}" for index in range(count)]
    groups = ["综合频道"] * count
    if include_cctv and count:
        names[0], groups[0] = "CCTV-1", "央视频道"
    if include_satellite and count > 1:
        names[1], groups[1] = "湖南卫视", "卫视频道"
    lines = ["#EXTM3U"]
    for index, (name, group) in enumerate(zip(names, groups)):
        lines.extend(
            [
                f'#EXTINF:-1 group-title="{group}",{name}',
                f"https://media.example/{index}.m3u8",
            ]
        )
    return ("\n".join(lines) + "\n").encode()


GOOD = b'''#EXTM3U x-tvg-url="https://epg.example/guide.xml.gz"\n#EXTINF:-1 group-title="\xe5\xa4\xae\xe8\xa7\x86\xe9\xa2\x91\xe9\x81\x93",CCTV-1\nhttps://media.example/cctv1.m3u8\n#EXTINF:-1 group-title="\xe5\x8d\xab\xe8\xa7\x86\xe9\xa2\x91\xe9\x81\x93",\xe6\xb9\x96\xe5\x8d\x97\xe5\x8d\xab\xe8\xa7\x86\nhttps://media.example/hunan.m3u8\n'''


class FakeHeaders:
    def __init__(self, content_type: str = "application/octet-stream"):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str = "application/octet-stream"):
        self.body = body
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1):
        return self.body if size < 0 else self.body[:size]


class LiveTests(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)

    def tearDown(self):
        self._temporary_directory.cleanup()

    def test_parse_preserves_metadata_and_groups(self):
        header, entries = parse_m3u(GOOD)
        self.assertIn("x-tvg-url", header)
        self.assertEqual(entries[0].name, "CCTV-1")
        self.assertEqual(entries[1].group, "卫视频道")

    def test_parse_merge_and_serialize_normalize_referer_metadata(self):
        raw = (
            b'#EXTM3U\n#EXTINF:-1 http-referer="https:/aptv.app/" '
            b'http-header="Referer=https:/live.example/",One\nhttps://media.example/one\n'
        )
        header, entries = parse_m3u(raw)
        self.assertEqual(header, "#EXTM3U")
        self.assertIn('http-referer="https://aptv.app/"', entries[0].info)
        self.assertIn('http-header="Referer=https://live.example/"', entries[0].info)
        self.assertEqual(
            merge_playlists([raw]),
            b'#EXTM3U\n#EXTINF:-1 http-referer="https://aptv.app/" '
            b'http-header="Referer=https://live.example/",One\nhttps://media.example/one\n',
        )

    def test_serialize_round_trips_entries_with_terminal_newline(self):
        raw = serialize_m3u(
            "#EXTM3U x-tvg-url=\"https://epg.example/guide.xml.gz\"",
            [M3UEntry('#EXTINF:-1 group-title="News"', "One", "https://a.example/one", "News")],
        )
        self.assertEqual(
            raw,
            b'#EXTM3U x-tvg-url="https://epg.example/guide.xml.gz"\n'
            b'#EXTINF:-1 group-title="News",One\nhttps://a.example/one\n',
        )
        self.assertEqual(parse_m3u(raw)[1][0].name, "One")

    def test_parser_rejects_invalid_encoding_structure_and_html(self):
        for raw, message in [
            (b"not-m3u", "#EXTM3U"),
            (b"#EXTM3U\nhttps://media.example/a.m3u8\n", "orphan URL"),
            (b"#EXTM3U\nfile:///a.m3u8\n", "orphan URL"),
            (b"#EXTM3U\n#EXTINF:-1,\nhttps://media.example/a.m3u8\n", "empty channel name"),
            (b"#EXTM3U\n#EXTINF:-1,One\nfile:///a.m3u8\n", "HTTP"),
            (b"#EXTM3U\n#EXTINF:-1,One\n<html>login</html>\n", "HTML"),
            (b"\xff\xfe", "UTF-8"),
        ]:
            with self.subTest(message=message):
                with self.assertRaisesRegex(PlaylistError, message):
                    parse_m3u(raw)

    def test_validation_rejects_html_duplicates_secrets_private_hosts_and_minimum(self):
        with self.assertRaisesRegex(PlaylistError, "HTML"):
            validate_playlist(b"<html>login</html>", "us")
        valid = make_playlist(20, include_cctv=True, include_satellite=True)
        duplicate = valid + b'#EXTINF:-1 group-title="\xe5\xa4\xae\xe8\xa7\x86\xe9\xa2\x91\xe9\x81\x93",CCTV-1\nhttps://media.example/0.m3u8\n'
        with self.assertRaisesRegex(PlaylistError, "duplicate channel/URL"):
            validate_playlist(duplicate, "us")
        secret = valid.replace(b"0.m3u8", b"0.m3u8?access_token=secret", 1)
        with self.assertRaisesRegex(PlaylistError, "sensitive query"):
            validate_playlist(secret, "us")
        private = valid.replace(b"media.example", b"192.168.1.20", 1)
        with self.assertRaisesRegex(PlaylistError, "private address"):
            validate_playlist(private, "us")
        with self.assertRaisesRegex(PlaylistError, "at least 20"):
            validate_playlist(make_playlist(19, False, False), "us")

    def test_validation_rejects_local_hosts_and_url_userinfo(self):
        valid = make_playlist(20, False, False)
        for host, message in [
            (b"127.0.0.1", "private address"),
            (b"station.local", "local hostname"),
            (b"station.lan", "local hostname"),
            (b"user:password@media.example", "URL userinfo"),
        ]:
            with self.subTest(host=host):
                raw = valid.replace(b"media.example", host, 1)
                with self.assertRaisesRegex(PlaylistError, message):
                    validate_playlist(raw, "us")

    def test_validation_rejects_sensitive_or_private_url_metadata(self):
        valid = make_playlist(20, False, False)
        secret_header = valid.replace(
            b"#EXTM3U",
            b'#EXTM3U x-tvg-url="https://epg.example/guide.xml?token=secret-value"',
        )
        with self.assertRaisesRegex(PlaylistError, "sensitive query"):
            validate_playlist(secret_header, "us")
        private_logo = valid.replace(
            b"#EXTINF:-1",
            b'#EXTINF:-1 tvg-logo="https://192.168.1.20/logo.png"',
            1,
        )
        with self.assertRaisesRegex(PlaylistError, "private address"):
            validate_playlist(private_logo, "us")

    def test_validation_rejects_unsafe_referer_metadata(self):
        valid = make_playlist(20, False, False)
        metadata_cases = [
            (b'http-referer="https://192.168.1.20/"', "private address"),
            (b'http-header="Referer=https://epg.example/guide?token=secret"', "sensitive query"),
            (b'http-header="Referer=ftp://unsupported.example/"', "HTTP"),
        ]
        for metadata, message in metadata_cases:
            with self.subTest(metadata=metadata):
                raw = valid.replace(b"#EXTINF:-1", b"#EXTINF:-1 " + metadata, 1)
                with self.assertRaisesRegex(PlaylistError, message):
                    validate_playlist(raw, "us")

    def test_validation_checks_each_x_tvg_and_url_tvg_url(self):
        valid = make_playlist(20, False, False)
        for attribute in (b"x-tvg-url", b"url-tvg"):
            with self.subTest(attribute=attribute):
                raw = valid.replace(
                    b"#EXTM3U",
                    b'#EXTM3U ' + attribute + b'="https://safe.example/a,https://192.168.1.1/b"',
                )
                with self.assertRaisesRegex(PlaylistError, "private address"):
                    validate_playlist(raw, "us")

    def test_validation_rejects_malformed_single_slash_referer(self):
        valid = make_playlist(20, False, False)
        raw = valid.replace(
            b"#EXTINF:-1",
            b'#EXTINF:-1 http-referer="https:/../foo"',
            1,
        )
        self.assertIn('http-referer="https:/../foo"', parse_m3u(raw)[1][0].info)
        with self.assertRaises(PlaylistError):
            validate_playlist(raw, "us")

    def test_validation_rejects_ambiguous_hosts_and_publishes_rejection_health(self):
        valid = make_playlist(20, False, False)
        for host in [b"localhost", b"2130706433", b"0x7f000001", b"0177.0.0.1", b"127.1", b"bad host"]:
            with self.subTest(host=host):
                with self.assertRaises(PlaylistError):
                    validate_playlist(valid.replace(b"media.example", host, 1), "us")

        destination = self.root / "auto-us.m3u"
        previous = make_playlist(40, False, False).replace(
            b"https://media.example/0.m3u8", b"https://[2001:db8::1"
        )
        destination.write_bytes(previous)
        report = publish_playlist(valid, destination, "us", self.root / "health.json")
        self.assertEqual(report.channel_count, 20)

        bad_port = valid.replace(b"media.example", b"media.example:99999", 1)
        with self.assertRaises(PlaylistError):
            publish_playlist(bad_port, destination, "us", self.root / "health.json")
        self.assertEqual(json.loads((self.root / "health.json").read_text(encoding="utf-8"))["status"], "rejected")

    def test_authority_malformed_current_is_rejected_and_previous_is_ignored(self):
        destination = self.root / "auto-us.m3u"
        health = self.root / "health.json"
        known_good = make_playlist(40, False, False)
        for authority in [b"media.example:", b"[2001:4860:4860::8888]junk"]:
            with self.subTest(authority=authority):
                malformed = make_playlist(20, False, False).replace(b"media.example", authority, 1)
                with self.assertRaises(PlaylistError):
                    validate_playlist(malformed, "us")
                destination.write_bytes(known_good)
                with self.assertRaises(PlaylistError):
                    publish_playlist(malformed, destination, "us", health)
                self.assertEqual(destination.read_bytes(), known_good)
                self.assertEqual(json.loads(health.read_text(encoding="utf-8"))["status"], "rejected")

                previous = make_playlist(40, False, False).replace(b"media.example", authority, 1)
                destination.write_bytes(previous)
                report = publish_playlist(make_playlist(20, False, False), destination, "us", health)
                self.assertEqual(report.channel_count, 20)

    def test_cn_requires_cctv_and_satellite_and_publish_is_atomic(self):
        many = make_playlist(40, include_cctv=True, include_satellite=True)
        destination = self.root / "auto-cn.m3u"
        destination.write_bytes(many)
        bad = make_playlist(20, include_cctv=True, include_satellite=True)
        health = self.root / "health.json"
        with self.assertRaisesRegex(PlaylistError, "channel drop"):
            publish_playlist(bad, destination, "cn", health)
        self.assertEqual(destination.read_bytes(), many)
        self.assertEqual(json.loads(health.read_text(encoding="utf-8"))["status"], "rejected")

    def test_cn_requires_mainland_groups(self):
        with self.assertRaisesRegex(PlaylistError, "CCTV"):
            validate_playlist(make_playlist(20, False, True), "cn")
        with self.assertRaisesRegex(PlaylistError, "卫视"):
            validate_playlist(make_playlist(20, True, False), "cn")

    def test_invalid_previous_playlist_does_not_trigger_drop_guardrail(self):
        destination = self.root / "auto-us.m3u"
        destination.write_bytes(make_playlist(40, False, False).replace(b"media.example", b"192.168.1.20"))
        report = publish_playlist(make_playlist(20, False, False), destination, "us", self.root / "health.json")
        self.assertEqual(report.channel_count, 20)

    def test_merge_keeps_first_seen_pairs_in_input_order(self):
        first = b"#EXTM3U first\n#EXTINF:-1 group-title=\"A\",One\nhttps://media.example/one\n"
        second = b"#EXTM3U second\n#EXTINF:-1 group-title=\"A\",One\nhttps://media.example/one\n#EXTINF:-1 group-title=\"B\",Two\nhttps://media.example/two\n"
        header, entries = parse_m3u(merge_playlists([first, second]))
        self.assertEqual(header, "#EXTM3U first")
        self.assertEqual([(entry.name, entry.url) for entry in entries], [("One", "https://media.example/one"), ("Two", "https://media.example/two")])

    def test_merge_deduplicates_casefolded_pairs_from_first_input(self):
        first = b"#EXTM3U\n#EXTINF:-1,One\nhttps://media.example/one\n#EXTINF:-1,ONE\nhttps://media.example/one\n"
        second = b"#EXTM3U\n#EXTINF:-1,one\nhttps://media.example/one\n#EXTINF:-1,Two\nhttps://media.example/two\n"
        _header, entries = parse_m3u(merge_playlists([first, second]))
        self.assertEqual([(entry.name, entry.url) for entry in entries], [("One", "https://media.example/one"), ("Two", "https://media.example/two")])

    def test_publication_uses_unique_same_directory_temporary_files(self):
        destination = self.root / "auto-us.m3u"
        health = self.root / "health.json"
        real_replace = os.replace
        temporary_paths: list[Path] = []

        def replace(source, target):
            temporary_paths.append(Path(source))
            return real_replace(source, target)

        with patch("hometv.live.os.replace", side_effect=replace):
            publish_playlist(make_playlist(20, False, False), destination, "us", health)
            publish_playlist(make_playlist(20, False, False), destination, "us", health)

        self.assertEqual(len(temporary_paths), 4)
        self.assertEqual(len(set(temporary_paths)), 4)
        self.assertTrue(all(path.parent == self.root for path in temporary_paths))
        self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_publish_acceptance_writes_report_and_sanitizes_rejection_error(self):
        destination = self.root / "auto-us.m3u"
        health = self.root / "health.json"
        report = publish_playlist(make_playlist(20, False, False), destination, "us", health)
        record = json.loads(health.read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["channel_count"], 20)
        self.assertEqual(record["sha256"], report.sha256)
        bad = make_playlist(20, False, False).replace(b"0.m3u8", b"0.m3u8?token=secret-value", 1)
        with self.assertRaises(PlaylistError):
            publish_playlist(bad, destination, "us", health)
        rejected = health.read_text(encoding="utf-8")
        self.assertIn('"status": "rejected"', rejected)
        self.assertNotIn("secret-value", rejected)

    @patch("urllib.request.urlopen")
    def test_fetch_enforces_response_requirements_and_hides_query_values(self, urlopen):
        urlopen.return_value = FakeResponse(b"#EXTM3U\n")
        self.assertEqual(fetch_live_bytes("https://media.example/list.m3u"), b"#EXTM3U\n")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "okhttp/4.12.0")

        urlopen.return_value = FakeResponse(b"<html>blocked</html>", "text/html")
        with self.assertRaisesRegex(PlaylistError, "HTML"):
            fetch_live_bytes("https://media.example/list.m3u")
        urlopen.side_effect = URLError("network token=secret-value")
        with self.assertRaises(PlaylistError) as captured:
            fetch_live_bytes("https://media.example/list.m3u?token=secret-value")
        self.assertNotIn("secret-value", str(captured.exception))

    @patch("urllib.request.urlopen")
    def test_fetch_rejects_non_200_empty_and_oversized_responses(self, urlopen):
        response = FakeResponse(b"#EXTM3U\n")
        response.status = 503
        urlopen.return_value = response
        with self.assertRaisesRegex(PlaylistError, "HTTP 503"):
            fetch_live_bytes("https://media.example/list.m3u")
        urlopen.return_value = FakeResponse(b"")
        with self.assertRaisesRegex(PlaylistError, "empty"):
            fetch_live_bytes("https://media.example/list.m3u")
        urlopen.return_value = FakeResponse(b"x" * (25 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(PlaylistError, "25 MiB"):
            fetch_live_bytes("https://media.example/list.m3u")


if __name__ == "__main__":
    unittest.main()
