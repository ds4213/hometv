from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from hometv.fetch import FetchedConfig
from hometv.refresh import RefreshError, promote_source, refresh_candidates, verify_regions
from hometv.registry import Source
from hometv.validate import ProbeResult


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
