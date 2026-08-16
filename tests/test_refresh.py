from datetime import datetime, timezone
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from hometv.fetch import FetchedConfig
import hometv.refresh as refresh
from hometv.live import PlaylistError
from hometv.refresh import RefreshError, promote_source, refresh_candidates, verify_regions
from hometv.registry import Source
from hometv.validate import ProbeResult


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_INPUTS = (
    "sources/registry.json",
    "sources/wanger-curated.json",
    "candidates/nitan-dm/upstream.json",
    "candidates/wangerxiao/upstream.json",
    "vendor/live/kimentanm.m3u",
)
GENERATED_PATHS = (
    "stable/us.json",
    "stable/cn.json",
    "stable/live-us.json",
    "stable/live-cn.json",
    "vendor/live/auto-us.m3u",
    "vendor/live/auto-cn.m3u",
)


def prepare_compose_root(root: Path) -> None:
    for relative in COMPOSE_INPUTS:
        source = REPOSITORY_ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def generated_snapshot(root: Path) -> dict[str, bytes]:
    return {
        relative: (root / relative).read_bytes()
        for relative in GENERATED_PATHS
        if (root / relative).exists()
    }


def seed_known_good_generated(root: Path) -> dict[str, bytes]:
    for relative in GENERATED_PATHS:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"known-good:{relative}".encode())
    return generated_snapshot(root)


def remove_candidate_key(root: Path, key: str) -> None:
    path = root / "candidates" / "wangerxiao" / "upstream.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["sites"] = [site for site in config["sites"] if site.get("key") != key]
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")


def fetched_candidate(source: Source, root: Path) -> FetchedConfig:
    content = json.loads(
        (root / "candidates" / source.id / "upstream.json").read_text(encoding="utf-8")
    )
    raw = json.dumps(content, ensure_ascii=False).encode()
    return FetchedConfig(
        source,
        content,
        raw,
        "2026-08-16T00:00:00+00:00",
        hashlib.sha256(raw).hexdigest(),
    )


def load_refresh_script():
    spec = importlib.util.spec_from_file_location(
        "hometv_refresh_script", REPOSITORY_ROOT / "scripts" / "refresh.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_live_playlist(channel_count: int) -> bytes:
    lines = ["#EXTM3U"]
    for index in range(channel_count):
        if index == 0:
            name, group = "CCTV1", "央视"
        elif index == 1:
            name, group = "北京卫视", "卫视"
        else:
            name, group = f"频道{index}", "其他"
        lines.extend(
            (
                f'#EXTINF:-1 group-title="{group}",{name}',
                f"https://media.example/{index}.m3u8",
            )
        )
    return ("\n".join(lines) + "\n").encode()


def write_registry(root: Path) -> None:
    path = root / "sources" / "registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "sources": [
                    {
                        "id": "example",
                        "name": "Example",
                        "url": "https://example.com/config.json",
                        "regions": ["us", "cn"],
                        "enabled": True,
                        "stable_regions": ["us", "cn"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def fetched(source: Source, config: dict) -> FetchedConfig:
    raw = json.dumps(config).encode()
    return FetchedConfig(
        source=source,
        content=config,
        raw=raw,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        sha256="abc123",
    )


class RefreshTests(unittest.TestCase):
    def test_compose_writes_six_outputs_only_after_all_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            nitan_count = len(
                json.loads(
                    (root / "candidates/nitan-dm/upstream.json").read_text(encoding="utf-8")
                )["sites"]
            )
            event = (root / "vendor/live/kimentanm.m3u").read_bytes().replace(
                b"rtmp://", b"http://"
            )

            result = refresh.compose_stable(
                root, mirror_func=Mock(), event_fetcher=lambda _url: event
            )

            self.assertEqual(
                result,
                ["stable/us.json", "stable/cn.json", "stable/live-us.json", "stable/live-cn.json"],
            )
            self.assertEqual(
                len(json.loads((root / "stable/us.json").read_text(encoding="utf-8"))["sites"]),
                nitan_count + 35,
            )
            self.assertEqual(set(generated_snapshot(root)), set(GENERATED_PATHS))
            self.assertNotIn(b"rtmp://", (root / "vendor/live/auto-us.m3u").read_bytes())

    def test_missing_wanger_key_keeps_all_known_good_generated_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            originals = seed_known_good_generated(root)
            remove_candidate_key(root, "SportAiKanqiu")

            with self.assertRaisesRegex(RefreshError, "missing curated keys: SportAiKanqiu"):
                refresh.compose_stable(root, mirror_func=Mock(), event_fetcher=lambda _url: b"")

            self.assertEqual(generated_snapshot(root), originals)

    def test_compose_falls_back_only_for_expected_event_network_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            seed = (root / "vendor/live/kimentanm.m3u").read_bytes()

            refresh.compose_stable(
                root,
                mirror_func=Mock(),
                event_fetcher=lambda _url: (_ for _ in ()).throw(urllib.error.URLError("offline")),
            )
            automatic = (root / "vendor/live/auto-us.m3u").read_bytes()
            self.assertNotIn(b"rtmp://", automatic)
            self.assertEqual(automatic.count(b"#EXTINF"), seed.count(b"#EXTINF") - 1)

            originals = seed_known_good_generated(root)
            with self.assertRaisesRegex(ValueError, "programming failure"):
                refresh.compose_stable(
                    root,
                    mirror_func=Mock(),
                    event_fetcher=lambda _url: (_ for _ in ()).throw(ValueError("programming failure")),
                )
            self.assertEqual(generated_snapshot(root), originals)

    def test_compose_rejects_more_than_35_percent_auto_playlist_drop_without_replacing_any_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            seed_known_good_generated(root)
            for region in ("us", "cn"):
                (root / f"vendor/live/auto-{region}.m3u").write_bytes(make_live_playlist(200))
            originals = generated_snapshot(root)

            with self.assertRaisesRegex(RefreshError, "channel drop exceeds 35%"):
                refresh.compose_stable(
                    root,
                    mirror_func=Mock(),
                    event_fetcher=lambda _url: (_ for _ in ()).throw(
                        urllib.error.URLError("offline")
                    ),
                )

            self.assertEqual(generated_snapshot(root), originals)

    def test_compose_falls_back_when_fetcher_wraps_http_error_in_playlist_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            wrapped = PlaylistError("live playlist returned HTTP 503")
            wrapped.__cause__ = urllib.error.HTTPError(
                "http://event.example/list.m3u", 503, "unavailable", None, None
            )

            refresh.compose_stable(
                root,
                mirror_func=Mock(),
                event_fetcher=lambda _url: (_ for _ in ()).throw(wrapped),
            )

            self.assertTrue((root / "vendor/live/auto-us.m3u").exists())

    def test_compose_does_not_swallow_non_network_file_or_permission_failures(self):
        for error in (OSError("local failure"), PermissionError("denied"), FileNotFoundError("missing")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                prepare_compose_root(root)
                originals = seed_known_good_generated(root)

                with self.assertRaises(type(error)):
                    refresh.compose_stable(
                        root,
                        mirror_func=Mock(),
                        event_fetcher=lambda _url, captured=error: (_ for _ in ()).throw(captured),
                    )

                self.assertEqual(generated_snapshot(root), originals)

    def test_compose_rolls_back_all_six_outputs_when_each_later_replace_fails(self):
        for failure_at in range(2, 7):
            with self.subTest(failure_at=failure_at), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                prepare_compose_root(root)
                originals = seed_known_good_generated(root)
                real_replace = os.replace
                primary_replacements = 0

                def fail_one_later_replace(source, destination):
                    nonlocal primary_replacements
                    source_path = Path(source)
                    if "rollback" not in source_path.parts:
                        primary_replacements += 1
                        if primary_replacements == failure_at:
                            raise OSError(f"replace {failure_at} failed")
                    return real_replace(source, destination)

                with patch("hometv.refresh.os.replace", side_effect=fail_one_later_replace):
                    with self.assertRaisesRegex(RefreshError, f"replace {failure_at} failed"):
                        refresh.compose_stable(
                            root,
                            mirror_func=Mock(),
                            event_fetcher=lambda _url: (_ for _ in ()).throw(
                                urllib.error.URLError("offline")
                            ),
                        )

                self.assertEqual(generated_snapshot(root), originals)

    def test_compose_keeps_existing_outputs_when_staged_json_cannot_be_reparsed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            originals = seed_known_good_generated(root)

            with patch("hometv.refresh._serialize", return_value="{"):
                with self.assertRaisesRegex(RefreshError, "unable to re-read staged stable/us.json"):
                    refresh.compose_stable(
                        root,
                        mirror_func=Mock(),
                        event_fetcher=lambda _url: (_ for _ in ()).throw(
                            urllib.error.URLError("offline")
                        ),
                    )

            self.assertEqual(generated_snapshot(root), originals)

    def test_candidate_refresh_rejects_invalid_wanger_before_writing_candidate_or_generated_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            originals = seed_known_good_generated(root)
            old_wanger = (root / "candidates/wangerxiao/upstream.json").read_bytes()
            bad_wanger = json.loads(old_wanger)
            bad_wanger["sites"] = [
                site for site in bad_wanger["sites"] if site.get("key") != "SportAiKanqiu"
            ]

            def fake_fetch(source: Source) -> FetchedConfig:
                if source.id == "wangerxiao":
                    return fetched(source, bad_wanger)
                return fetched_candidate(source, root)

            result = refresh_candidates(root, fetcher=fake_fetch, mirror_func=Mock())
            wanger = next(item for item in result if item["source"] == "wangerxiao")
            self.assertEqual(wanger["status"], "failed")
            self.assertIn("missing curated keys: SportAiKanqiu", wanger["message"])
            self.assertEqual((root / "candidates/wangerxiao/upstream.json").read_bytes(), old_wanger)
            self.assertEqual(generated_snapshot(root), originals)

    def test_candidate_refresh_never_changes_policy_stable_or_auto_playlists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare_compose_root(root)
            originals = seed_known_good_generated(root)
            policy_before = (root / "sources/wanger-curated.json").read_bytes()

            refresh_candidates(
                root,
                fetcher=lambda source: fetched_candidate(source, root),
                mirror_func=Mock(),
            )

            self.assertEqual(generated_snapshot(root), originals)
            self.assertEqual((root / "sources/wanger-curated.json").read_bytes(), policy_before)

    def test_verify_reads_live_config_and_probes_live_urls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stable = root / "stable"
            stable.mkdir(parents=True)
            (stable / "us.json").write_text(
                json.dumps({"spider": "https://vod.example/spider.jar", "sites": [], "lives": []}),
                encoding="utf-8",
            )
            (stable / "live-us.json").write_text(
                json.dumps(
                    {
                        "lives": [
                            {
                                "name": "Auto",
                                "url": "https://live.example/auto.m3u",
                                "boot": True,
                                "ua": "okhttp/4.12.0",
                                "timeout": 15,
                            },
                            {
                                "name": "Event",
                                "url": "http://event.example/list.m3u",
                                "boot": False,
                                "ua": "okhttp/4.12.0",
                                "timeout": 15,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            seen: list[str] = []

            def prober(url: str) -> ProbeResult:
                seen.append(url)
                return ProbeResult(url, True, 200, 1, 1, "sha", "text/plain", "", "")

            statuses = verify_regions(root, ("us",), network=True, prober=prober)
            health = json.loads((root / "health/us.json").read_text(encoding="utf-8"))
            self.assertEqual(statuses["us"], "warning")
            self.assertIn("https://live.example/auto.m3u", seen)
            self.assertIn("http://event.example/list.m3u", seen)
            self.assertIn("cleartext-http", {item["code"] for item in health["findings"]})

    def test_verify_collects_schema_urls_once_across_vod_and_live_documents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stable = root / "stable"
            stable.mkdir(parents=True)
            shared = "https://shared.example/spider.jar"
            (stable / "us.json").write_text(
                json.dumps(
                    {
                        "spider": f"{shared};md5;0123456789abcdef0123456789abcdef",
                        "sites": [
                            {
                                "api": "https://api.example/vod",
                                "jar": f"{shared};md5;0123456789abcdef0123456789abcdef",
                                "ext": {
                                    "plain": "not a URL",
                                    "nested": ["https://ext.example/one", {"url": "https://ext.example/two"}],
                                },
                            },
                            {
                                "jar": f"{shared};md5;0123456789abcdef0123456789abcdef",
                            },
                        ],
                        "doh": [{"url": "https://dns.example/dns-query"}],
                        "wallpaper": "https://wall.example/wallpaper.jpg",
                        "lives": [],
                    }
                ),
                encoding="utf-8",
            )
            (stable / "live-us.json").write_text(
                json.dumps(
                    {
                        "lives": [
                            {
                                "name": "Auto",
                                "url": shared,
                                "boot": True,
                                "ua": "okhttp/4.12.0",
                                "timeout": 15,
                                "epg": "https://epg.example/one.xml,https://epg.example/two.xml",
                                "nested": {"url": "https://live-nested.example/list.m3u"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            seen: list[str] = []

            def prober(url: str) -> ProbeResult:
                seen.append(url)
                return ProbeResult(url, True, 200, 1, 1, "sha", "text/plain", "", "")

            statuses = verify_regions(root, ("us",), network=True, prober=prober)

            self.assertEqual(statuses["us"], "ok")
            self.assertEqual(seen.count(shared), 1)
            self.assertIn("https://ext.example/one", seen)
            self.assertIn("https://ext.example/two", seen)
            self.assertIn("https://dns.example/dns-query", seen)
            self.assertIn("https://wall.example/wallpaper.jpg", seen)
            self.assertIn("https://epg.example/one.xml", seen)
            self.assertIn("https://epg.example/two.xml", seen)
            self.assertIn("https://live-nested.example/list.m3u", seen)
            self.assertNotIn("not a URL", seen)

    def test_verify_keeps_mainland_repository_urls_as_pending_information(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stable = root / "stable"
            stable.mkdir(parents=True)
            gitee_url = "https://gitee.com/ds4213tv/hometv/raw/main/vendor/live/auto-cn.m3u"
            (stable / "cn.json").write_text(
                json.dumps({"spider": gitee_url, "sites": [], "lives": []}), encoding="utf-8"
            )
            (stable / "live-cn.json").write_text(
                json.dumps(
                    {
                        "lives": [
                            {
                                "name": "Auto",
                                "url": gitee_url,
                                "boot": True,
                                "ua": "okhttp/4.12.0",
                                "timeout": 15,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            probed: list[str] = []

            statuses = verify_regions(
                root,
                ("cn",),
                network=True,
                prober=lambda url: probed.append(url),
            )
            health = json.loads((root / "health/cn.json").read_text(encoding="utf-8"))

            self.assertEqual(statuses["cn"], "ok")
            self.assertEqual(probed, [])
            pending = [item for item in health["findings"] if item["code"] == "gitee-sync-pending"]
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["path"], "$.spider")

    def test_compose_cli_prints_the_composed_paths(self):
        module = load_refresh_script()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(module, "compose_stable", return_value=["stable/us.json"]) as compose:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = module.main(["--root", temp_dir, "compose"])
            self.assertEqual(result, 0)
            compose.assert_called_once_with(Path(temp_dir).resolve())
            self.assertEqual(json.loads(output.getvalue()), {"composed": ["stable/us.json"]})

    def test_publish_live_cli_maps_cn_and_keeps_destination_on_playlist_error(self):
        module = load_refresh_script()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.m3u"
            source.write_bytes(b"bad input")
            destination = root / "vendor/live/auto-cn.m3u"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"known good")
            with patch.object(module, "publish_playlist", side_effect=PlaylistError("bad playlist")) as publish:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = module.main(
                        ["--root", str(root), "publish-live", "--profile", "cn", "--input", str(source)]
                    )
            self.assertEqual(result, 1)
            publish.assert_called_once_with(
                b"bad input", destination.resolve(), "cn", (root / "health/live-cn.json").resolve()
            )
            self.assertEqual(destination.read_bytes(), b"known good")

    def test_network_verification_retries_one_transient_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stable = root / "stable" / "us.json"
            stable.parent.mkdir(parents=True)
            stable.write_text(
                json.dumps(
                    {
                        "spider": "https://example.com/spider.jar",
                        "sites": [],
                        "lives": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "stable" / "live-us.json").write_text(
                json.dumps(
                    {
                        "lives": [
                            {
                                "name": "Auto",
                                "url": "https://example.com/spider.jar",
                                "boot": True,
                                "ua": "okhttp/4.12.0",
                                "timeout": 15,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            calls = 0

            def flaky_probe(url):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return ProbeResult(url, False, 0, 0, 0, "", "", "timed out", "")
                return ProbeResult(url, True, 200, 10, 2, "abc", "application/json", "", "")

            statuses = verify_regions(
                root,
                ("us",),
                network=True,
                prober=flaky_probe,
            )

            self.assertEqual(calls, 2)
            self.assertEqual(statuses["us"], "ok")

    def test_candidate_refresh_never_writes_stable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_registry(root)

            def fake_fetch(source):
                return fetched(source, {"spider": "https://example.com/spider.jar", "sites": [], "lives": []})

            result = refresh_candidates(root, fetcher=fake_fetch)
            self.assertEqual(result[0]["status"], "updated")
            self.assertTrue((root / "candidates" / "example" / "upstream.json").exists())
            self.assertFalse((root / "stable").exists())

    def test_mainland_candidate_refreshes_mirrored_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_registry(root)

            def fake_fetch(source):
                return fetched(
                    source,
                    {
                        "spider": "https://github.com/nitan-tv/nitan/raw/refs/heads/main/awdm.png",
                        "sites": [],
                        "lives": [],
                    },
                )

            def fake_mirror(requests, mirror_root):
                for request in requests:
                    path = mirror_root / request.repository_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"mirrored")
                return {"files": []}

            refresh_candidates(root, fetcher=fake_fetch, mirror_func=fake_mirror)
            self.assertEqual((root / "vendor" / "nitan" / "awdm.png").read_bytes(), b"mirrored")

    def test_promotion_writes_both_regions_after_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_registry(root)
            config = {"spider": "https://example.com/spider.jar", "sites": [], "lives": []}
            candidate = root / "candidates" / "example" / "upstream.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps(config), encoding="utf-8")

            def fake_mirror(_requests, _root):
                return {"files": []}

            promoted = promote_source(root, "example", ("us", "cn"), mirror_func=fake_mirror)
            self.assertEqual(set(promoted), {"us", "cn"})
            self.assertTrue((root / "stable" / "us.json").exists())
            self.assertTrue((root / "stable" / "cn.json").exists())

    def test_failed_promotion_keeps_known_good_stable_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_registry(root)
            candidate = root / "candidates" / "example" / "upstream.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps({"spider": "", "sites": [], "lives": []}), encoding="utf-8")
            stable = root / "stable" / "us.json"
            stable.parent.mkdir(parents=True)
            stable.write_text('{"known":"good"}', encoding="utf-8")

            with self.assertRaisesRegex(RefreshError, "validation failed"):
                promote_source(root, "example", ("us",), mirror_func=lambda *_args: {})
            self.assertEqual(stable.read_text(encoding="utf-8"), '{"known":"good"}')


if __name__ == "__main__":
    unittest.main()
