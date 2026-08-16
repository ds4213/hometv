# Curated Wang Er Xiao and FongMi Live Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish parent-friendly US and mainland FongMi configurations that keep Nitan as the global Spider, add exactly 35 curated Wang Er Xiao sites with an isolated Spider, and expose dedicated, non-empty regional LiveConfig URLs.

**Architecture:** Treat upstream JSON as candidates and compose four stable artifacts only through an explicit, atomic promotion command. A focused curation module owns Wang selection and Spider isolation, while a focused live module owns M3U parsing, guardrails, seeding, and publication. Regional URL rewriting remains in the build layer; validation and health reporting cover Vod and Live artifacts independently.

**Tech Stack:** Python 3.12 standard library, `unittest`, JSON, M3U text, GitHub Actions, Git, FongMi 5.6.1.

## Global Constraints

- Keep the permanent Vod URLs at `stable/cn.json` and `stable/us.json`.
- Add permanent Live URLs at `stable/live-cn.json` and `stable/live-us.json`.
- Nitan remains the top-level `spider`; every selected Wang `type=3` site gets its own `jar`.
- Select exactly the 35 keys approved in the design; the allowlist is data, not Python logic.
- Preserve upstream site order and every site field except the intentional `name` prefix and `jar` override.
- A missing, duplicate, or colliding curated key aborts composition and leaves all current stable files unchanged.
- Mainland repository-owned URLs use Gitee Raw; US repository-owned URLs use GitHub Raw.
- Mainland stable JSON must contain no `github.com` or `raw.githubusercontent.com` dependency.
- Each LiveConfig has exactly three sources in this order: regional automatic, mirrored Kimentanm, direct event fallback.
- Seed `auto-cn.m3u` and `auto-us.m3u` before NAS automation is enabled.
- Reject M3U output that is HTML, malformed, has fewer than 20 distinct channels, drops more than 35%, contains secrets/private addresses, or duplicates a channel/URL pair.
- Candidate refresh may update candidates, mirrors, and health only; it may not change the allowlist, stable JSON, or automatic playlists.
- Do not commit cookies, access tokens, cloud-drive credentials, Emby credentials, WebDAV credentials, or personal server keys.

---

## File Structure

- Create `sources/wanger-curated.json`: ordered curation policy and display prefix.
- Create `hometv/curation.py`: strict allowlist loading, Wang site selection, Spider reference parsing, and collision-safe merging.
- Create `hometv/live.py`: M3U parsing/serialization, playlist guardrails, seed merge, and atomic publication.
- Modify `hometv/build.py`: hash-aware mirror requests, regional Wang composition, and LiveConfig construction.
- Modify `hometv/refresh.py`: explicit four-artifact composition, candidate protection, regional verification, and live publication orchestration.
- Modify `hometv/validate.py`: dedicated LiveConfig validation.
- Modify `scripts/refresh.py`: `compose` and `publish-live` commands.
- Create `tests/test_curation.py` and `tests/test_live.py`; extend the existing build, refresh, and validation tests.
- Generate `vendor/wanger/spider.jpg`, `vendor/live/auto-cn.m3u`, `vendor/live/auto-us.m3u`, `stable/live-cn.json`, and `stable/live-us.json`.
- Modify `README.md` and `.github/workflows/refresh-candidates.yml`: permanent URLs, safe operations, and regression checks.

### Task 1: Declarative Wang Curation

**Files:**
- Create: `sources/wanger-curated.json`
- Create: `hometv/curation.py`
- Create: `tests/test_curation.py`

**Interfaces:**
- Produces: `CurationError(RuntimeError)`.
- Produces: `CuratedSource(source_id: str, name_prefix: str, keys: tuple[str, ...])`.
- Produces: `load_curated_source(path: Path) -> CuratedSource`.
- Produces: `parse_spider_reference(reference: str) -> tuple[str, str, str]`, returning source URL, algorithm, digest.
- Produces: `select_curated_sites(config: dict, policy: CuratedSource, jar: str) -> list[dict]`.
- Produces: `merge_curated_sites(base: dict, selected: list[dict]) -> dict`.

- [ ] **Step 1: Write failing policy and selection tests**

```python
class CurationTests(unittest.TestCase):
    def test_real_policy_contains_exact_approved_keys(self):
        policy = load_curated_source(Path("sources/wanger-curated.json"))
        self.assertEqual(policy.source_id, "wangerxiao")
        self.assertEqual(policy.name_prefix, "🐮")
        self.assertEqual(len(policy.keys), 35)
        self.assertEqual(len(set(policy.keys)), 35)

    def test_selection_preserves_upstream_order_and_fields(self):
        policy = CuratedSource("wangerxiao", "🐮", ("b", "a"))
        upstream = {"sites": [
            {"key": "a", "name": "A", "type": 3, "api": "csp_A", "ext": {"x": 1}},
            {"key": "ignored", "name": "I", "type": 3, "api": "csp_I"},
            {"key": "b", "name": "B", "type": 3, "api": "csp_B", "timeout": 120},
        ]}
        selected = select_curated_sites(upstream, policy, "https://repo/spider.jpg;md5;abc")
        self.assertEqual([site["key"] for site in selected], ["a", "b"])
        self.assertEqual(selected[0]["ext"], {"x": 1})
        self.assertEqual(selected[1]["timeout"], 120)
        self.assertTrue(all(site["name"].startswith("🐮") for site in selected))
        self.assertTrue(all(site["jar"].endswith(";md5;abc") for site in selected))

    def test_missing_duplicate_or_base_collision_is_rejected(self):
        policy = CuratedSource("wangerxiao", "🐮", ("a", "b"))
        with self.assertRaisesRegex(CurationError, "missing curated keys: b"):
            select_curated_sites({"sites": [{"key": "a", "name": "A", "type": 3}]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "duplicate upstream key: a"):
            select_curated_sites({"sites": [
                {"key": "a", "name": "A", "type": 3},
                {"key": "a", "name": "A2", "type": 3},
                {"key": "b", "name": "B", "type": 3},
            ]}, policy, "jar")
        with self.assertRaisesRegex(CurationError, "site key collision: a"):
            merge_curated_sites({"spider": "nitan", "sites": [{"key": "a"}]}, [{"key": "a"}])
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `python -m unittest tests.test_curation -v`

Expected: FAIL because `hometv.curation` and the policy file do not exist.

- [ ] **Step 3: Add the exact policy file**

```json
{
  "schema": 1,
  "source_id": "wangerxiao",
  "name_prefix": "🐮",
  "keys": [
    "二小", "玩偶", "AiNewGuanYing", "AiQwMkv", "NewZhiZhen", "AiNewLibvio",
    "WexHanXiaoQuan", "WexAiGuaZi", "WexAiDuBoKu", "WexAiYueYue", "WexAiWenCai",
    "WexAiV6DaShiXiong", "WexAiV6TeGou", "賤賤", "WexAiYiYs", "WexAiReBo",
    "WexAiBoBo", "WexAiIkanBot", "DuanJuAiHaoKan", "DuanJuAiQiMiao", "DuanJuAiXingYa",
    "AnimeXiFan", "AnimeCiYuanCheng", "AnimeAiMiaoWu", "ChildrenAiBaoBao", "ChildrenAiBeiWa",
    "少儿教育", "小学课堂", "MusicAiLiYuan", "MusicAiIKtv", "MusicAiKuWo",
    "SportAiFeiQiu", "SportAiGuaZi", "SportAiKanQiuTong", "SportAiKanqiu"
  ]
}
```

- [ ] **Step 4: Implement strict loading and selection**

Implement the declared interfaces using deep copies. `load_curated_source` rejects schema values other than `1`, empty prefixes, non-string keys, and duplicate keys. `select_curated_sites` first indexes the complete upstream `sites` array to expose duplicates, then filters in upstream order, requires `type == 3`, applies `name = prefix + original_name`, and sets `jar` without changing any other field. `parse_spider_reference` accepts only `URL;md5;32-hex-digest`.

- [ ] **Step 5: Run the focused tests**

Run: `python -m unittest tests.test_curation -v`

Expected: PASS with the real file reporting 35 unique keys.

- [ ] **Step 6: Commit**

```powershell
git add sources/wanger-curated.json hometv/curation.py tests/test_curation.py
git commit -m "Add curated Wang source policy"
```

### Task 2: Hash-Checked Wang Spider and Regional Vod Composition

**Files:**
- Modify: `hometv/build.py`
- Modify: `tests/test_build.py`

**Interfaces:**
- Changes: `MirrorRequest(source_url: str, repository_path: str, expected_md5: str = "")`.
- Produces: `build_curated_vod(nitan: dict, wanger: dict, policy: CuratedSource, region: str, github_base: str, gitee_base: str) -> BuildResult`.
- Consumes: all Task 1 interfaces.

- [ ] **Step 1: Add failing regional-isolation and hash tests**

```python
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
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m unittest tests.test_build -v`

Expected: FAIL because `MirrorRequest` lacks `expected_md5` and `build_curated_vod` is undefined.

- [ ] **Step 3: Implement digest verification before atomic replacement**

Calculate `hashlib.md5(raw).hexdigest()` only when `expected_md5` is non-empty. Raise `BuildError(f"{item.source_url}: MD5 mismatch")` before writing the temporary file. Keep SHA-256 in `vendor/manifest.json` and add `expected_md5` plus `md5` to the Wang manifest record.

- [ ] **Step 4: Implement regional composition**

Use existing `build_us`/`build_cn` for the Nitan base. Parse Wang's Spider, build a `MirrorRequest` for `vendor/wanger/spider.jpg`, and construct the regional repository URL with `f"{regional_url};md5;{digest}"`. Select the curated sites and collision-safely append them. Return Nitan mirror requests first and the Wang request last. Do not copy Wang `parses`, `doh`, `rules`, `ads`, or `lives` into the Nitan base.

- [ ] **Step 5: Run build and curation tests**

Run: `python -m unittest tests.test_build tests.test_curation -v`

Expected: PASS; both regional Wang sites use per-site `jar`, and Nitan remains the global Spider.

- [ ] **Step 6: Commit**

```powershell
git add hometv/build.py tests/test_build.py
git commit -m "Compose isolated Wang sites"
```

### Task 3: M3U Parser, Guardrails, and Seed Playlists

**Files:**
- Create: `hometv/live.py`
- Create: `tests/test_live.py`

**Interfaces:**
- Produces: `PlaylistError(RuntimeError)`.
- Produces: `M3UEntry(info: str, name: str, url: str, group: str)`.
- Produces: `PlaylistReport(profile: str, channel_count: int, url_count: int, groups: tuple[str, ...], sha256: str)`.
- Produces: `parse_m3u(raw: bytes) -> tuple[str, list[M3UEntry]]`.
- Produces: `serialize_m3u(header: str, entries: list[M3UEntry]) -> bytes`.
- Produces: `validate_playlist(raw: bytes, profile: str, previous: bytes | None = None) -> PlaylistReport`.
- Produces: `merge_playlists(raw_items: list[bytes]) -> bytes`.
- Produces: `publish_playlist(raw: bytes, destination: Path, profile: str, health_path: Path) -> PlaylistReport`.
- Produces: `fetch_live_bytes(url: str, timeout: float = 20.0) -> bytes`.

- [ ] **Step 1: Write failing parser and guardrail tests**

```python
def make_playlist(count: int, include_cctv: bool, include_satellite: bool) -> bytes:
    names = [f"频道{i:02d}" for i in range(count)]
    groups = ["综合频道"] * count
    if include_cctv and count:
        names[0], groups[0] = "CCTV-1", "央视频道"
    if include_satellite and count > 1:
        names[1], groups[1] = "湖南卫视", "卫视频道"
    lines = ["#EXTM3U"]
    for index, (name, group) in enumerate(zip(names, groups)):
        lines.extend([
            f'#EXTINF:-1 group-title="{group}",{name}',
            f"https://media.example/{index}.m3u8",
        ])
    return ("\n".join(lines) + "\n").encode()

GOOD = b'''#EXTM3U x-tvg-url="https://epg.example/guide.xml.gz"\n#EXTINF:-1 group-title="央视频道",CCTV-1\nhttps://media.example/cctv1.m3u8\n#EXTINF:-1 group-title="卫视频道",湖南卫视\nhttps://media.example/hunan.m3u8\n'''

def test_parse_preserves_metadata_and_groups(self):
    header, entries = parse_m3u(GOOD)
    self.assertIn("x-tvg-url", header)
    self.assertEqual(entries[0].name, "CCTV-1")
    self.assertEqual(entries[1].group, "卫视频道")

def test_validation_rejects_html_duplicates_secrets_private_hosts_and_large_drop(self):
    with self.assertRaisesRegex(PlaylistError, "HTML"):
        validate_playlist(b"<html>login</html>", "us")
    valid = make_playlist(20, include_cctv=True, include_satellite=True)
    duplicate = valid + b'#EXTINF:-1 group-title="央视频道",CCTV-1\nhttps://media.example/0.m3u8\n'
    with self.assertRaisesRegex(PlaylistError, "duplicate channel/URL"):
        validate_playlist(duplicate, "us")
    secret = valid.replace(b"0.m3u8", b"0.m3u8?access_token=secret", 1)
    with self.assertRaisesRegex(PlaylistError, "sensitive query"):
        validate_playlist(secret, "us")
    private = valid.replace(b"media.example", b"192.168.1.20", 1)
    with self.assertRaisesRegex(PlaylistError, "private address"):
        validate_playlist(private, "us")

def test_cn_requires_cctv_and_satellite_and_publish_is_atomic(self):
    many = make_playlist(40, include_cctv=True, include_satellite=True)
    destination = self.root / "auto-cn.m3u"
    destination.write_bytes(many)
    bad = make_playlist(20, include_cctv=True, include_satellite=True)
    with self.assertRaisesRegex(PlaylistError, "channel drop"):
        publish_playlist(bad, destination, "cn", self.root / "health.json")
    self.assertEqual(destination.read_bytes(), many)
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run: `python -m unittest tests.test_live -v`

Expected: FAIL because `hometv.live` does not exist.

- [ ] **Step 3: Implement strict parsing and serialization**

Require a UTF-8/UTF-8-BOM document whose first non-empty line starts with `#EXTM3U`. Pair every `#EXTINF` line with exactly one subsequent HTTP(S) media URL. Extract the display name after the final comma and `group-title` with `re`. Reject orphan URLs, missing URLs, empty names, non-HTTP(S) URLs, and HTML prefixes. Serialize with `\n` endings and one terminal newline.

- [ ] **Step 4: Implement exact publication guardrails**

Count distinct normalized channel names and distinct URLs. Reject fewer than 20 channels. When `previous` exists and is valid, reject `(previous_count - new_count) / previous_count > 0.35`. Reject duplicate `(casefold(name), url)` pairs, URL userinfo, loopback/link-local/private/reserved IP literals, hostnames ending `.local` or `.lan`, and non-empty query keys `token`, `access_token`, `auth`, `authorization`, `password`, `passwd`, `secret`, `signature`, or `sig`. For `cn`, require a channel beginning `CCTV` and a channel or group containing `卫视`.

- [ ] **Step 5: Implement deterministic merge and atomic publication**

`merge_playlists` keeps the first header, retains first-seen `(name, url)` pairs, and preserves input order. `publish_playlist` validates against the current destination, writes `destination.with_name(destination.name + ".tmp")`, parses it again, replaces the destination, and atomically writes health JSON containing `generated_at`, `profile`, counts, groups, SHA-256, and `status: "accepted"`. A rejection writes `status: "rejected"` and the sanitized error to health without replacing the destination.

`fetch_live_bytes` sends `User-Agent: okhttp/4.12.0`, requires HTTP 200, caps the response at 25 MiB, rejects empty or HTML responses, and returns raw bytes. It converts `OSError` and `urllib.error.URLError` into `PlaylistError` without including URL query values in the error.

- [ ] **Step 6: Run live tests**

Run: `python -m unittest tests.test_live -v`

Expected: PASS, including minimum-count, 35% drop, mainland-group, secret, duplicate, and atomic-rejection coverage.

- [ ] **Step 7: Commit**

```powershell
git add hometv/live.py tests/test_live.py
git commit -m "Add guarded live playlist publication"
```

### Task 4: Dedicated Regional LiveConfig Artifacts

**Files:**
- Modify: `hometv/build.py`
- Modify: `hometv/validate.py`
- Modify: `tests/test_build.py`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Produces: `build_live_config(region: str, github_base: str, gitee_base: str) -> dict`.
- Produces: `validate_live_config(config: dict, region: str) -> list[Finding]`.

- [ ] **Step 1: Add failing shape, order, and mainland dependency tests**

```python
GITHUB = "https://raw.githubusercontent.com/ds4213/hometv/main"
GITEE = "https://gitee.com/ds4213tv/hometv/raw/main"

def test_live_configs_have_three_ordered_sources(self):
    cn = build_live_config("cn", GITHUB, GITEE)
    us = build_live_config("us", GITHUB, GITEE)
    self.assertEqual([item["name"] for item in cn["lives"]], ["HomeTV 自动（中国）", "HomeTV 备用（Kimentanm）", "HomeTV 临时赛事"])
    self.assertTrue(cn["lives"][0]["boot"])
    self.assertEqual(sum(bool(item.get("boot")) for item in cn["lives"]), 1)
    self.assertIn("vendor/live/auto-cn.m3u", cn["lives"][0]["url"])
    self.assertIn("vendor/live/auto-us.m3u", us["lives"][0]["url"])
    self.assertNotIn("github", json.dumps(cn).lower())
    self.assertEqual(cn["lives"][1]["epg"], "https://epg.aptv.app/pp.xml.gz,https://epg.aptv.app/xml")
    self.assertEqual(cn["lives"][2]["epg"], "https://epg.zsdc.eu.org/t.xml")

def test_live_validation_requires_unique_names_urls_ua_timeout_and_one_boot(self):
    config = {"lives": [{"name": "A", "url": "https://one", "boot": True, "ua": "okhttp/4.12.0", "timeout": 15}]}
    self.assertEqual(validate_live_config(config, "us"), [])
    broken = {"lives": [config["lives"][0], dict(config["lives"][0])]}
    codes = {finding.code for finding in validate_live_config(broken, "us")}
    self.assertIn("duplicate-live-name", codes)
    self.assertIn("duplicate-live-url", codes)
    self.assertIn("invalid-live-boot-count", codes)
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m unittest tests.test_build tests.test_validate -v`

Expected: FAIL because the new builders and validators are undefined.

- [ ] **Step 3: Implement exact LiveConfig construction**

Each entry contains `name`, `url`, `boot`, `ua: "okhttp/4.12.0"`, and `timeout: 15`. The Kimentanm entry also contains `epg: "https://epg.aptv.app/pp.xml.gz,https://epg.aptv.app/xml"`; the event entry contains `epg: "https://epg.zsdc.eu.org/t.xml"`. Use `http://82.156.243.185:33389/fwc.m3u` only for the third entry. Set `boot: true` only on the first entry.

- [ ] **Step 4: Implement independent LiveConfig validation**

Require a top-level object and a non-empty `lives` list. Require unique non-empty names and URLs, one and only one `boot: true`, non-empty `ua`, integer `timeout >= 1`, and HTTP(S) URLs. Reuse the mainland GitHub-host check and cleartext warning semantics from `validate_config`.

- [ ] **Step 5: Run focused tests**

Run: `python -m unittest tests.test_build tests.test_validate -v`

Expected: PASS with no errors for either generated LiveConfig; the only expected finding is the cleartext warning for the temporary event URL.

- [ ] **Step 6: Commit**

```powershell
git add hometv/build.py hometv/validate.py tests/test_build.py tests/test_validate.py
git commit -m "Add dedicated regional live configs"
```

### Task 5: Safe Four-Artifact Composition and CLI

**Files:**
- Modify: `hometv/refresh.py`
- Modify: `scripts/refresh.py`
- Modify: `tests/test_refresh.py`

**Interfaces:**
- Produces: `compose_stable(root: Path, mirror_func: Callable = mirror_files, event_fetcher: Callable[[str], bytes] = fetch_live_bytes) -> list[str]`.
- Produces CLI: `python scripts/refresh.py compose`.
- Produces CLI examples: `python scripts/refresh.py publish-live --profile us --input ops/iptv-api/profiles/us/output/ipv4/result.m3u` and the corresponding `cn` path.
- Changes: `verify_regions(...)` reads and reports on `stable/us.json`, `stable/cn.json`, `stable/live-us.json`, and `stable/live-cn.json`.

- [ ] **Step 1: Add failing no-partial-write and candidate-safety tests**

```python
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_INPUTS = (
    "sources/registry.json",
    "sources/wanger-curated.json",
    "candidates/nitan-dm/upstream.json",
    "candidates/wangerxiao/upstream.json",
    "vendor/live/kimentanm.m3u",
)
GENERATED_PATHS = (
    "stable/us.json", "stable/cn.json",
    "stable/live-us.json", "stable/live-cn.json",
    "vendor/live/auto-us.m3u", "vendor/live/auto-cn.m3u",
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
    path = root / "candidates/wangerxiao/upstream.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["sites"] = [site for site in config["sites"] if site.get("key") != key]
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

def fetched_candidate(source: Source, root: Path) -> FetchedConfig:
    content = json.loads((root / "candidates" / source.id / "upstream.json").read_text(encoding="utf-8"))
    raw = json.dumps(content, ensure_ascii=False).encode()
    return FetchedConfig(source, content, raw, "2026-08-16T00:00:00+00:00", hashlib.sha256(raw).hexdigest())

def test_compose_writes_four_artifacts_only_after_all_validation(self):
    prepare_compose_root(self.root)
    nitan_count = len(json.loads((self.root / "candidates/nitan-dm/upstream.json").read_text(encoding="utf-8"))["sites"])
    mirror = Mock()
    event = (self.root / "vendor/live/kimentanm.m3u").read_bytes()
    result = compose_stable(self.root, mirror_func=mirror, event_fetcher=lambda _: event)
    self.assertEqual(result, ["stable/us.json", "stable/cn.json", "stable/live-us.json", "stable/live-cn.json"])
    self.assertEqual(len(json.loads((self.root / "stable/us.json").read_text())["sites"]), nitan_count + 35)

def test_missing_wanger_key_keeps_all_known_good_stable_files(self):
    prepare_compose_root(self.root)
    originals = seed_known_good_generated(self.root)
    remove_candidate_key(self.root, "SportAiKanqiu")
    with self.assertRaisesRegex(RefreshError, "missing curated keys: SportAiKanqiu"):
        compose_stable(self.root, mirror_func=Mock(), event_fetcher=lambda _: b"")
    self.assertEqual(generated_snapshot(self.root), originals)

def test_candidate_refresh_never_changes_policy_stable_or_auto_playlists(self):
    prepare_compose_root(self.root)
    originals = seed_known_good_generated(self.root)
    policy_before = (self.root / "sources/wanger-curated.json").read_bytes()
    refresh_candidates(
        self.root,
        fetcher=lambda source: fetched_candidate(source, self.root),
        mirror_func=Mock(),
    )
    self.assertEqual(generated_snapshot(self.root), originals)
    self.assertEqual((self.root / "sources/wanger-curated.json").read_bytes(), policy_before)
```

- [ ] **Step 2: Run the refresh tests and verify failure**

Run: `python -m unittest tests.test_refresh -v`

Expected: FAIL because `compose_stable` and the new CLI routes are undefined.

- [ ] **Step 3: Implement composition staging**

Load `candidates/nitan-dm/upstream.json`, `candidates/wangerxiao/upstream.json`, and `sources/wanger-curated.json`. Build both curated Vod configs and both LiveConfigs. Fetch/hash-check all mirror requests before stable staging. Seed each automatic playlist by merging the existing repository Kimentanm file and `event_fetcher("http://82.156.243.185:33389/fwc.m3u")`; if that fetch raises an expected network exception, seed from Kimentanm alone. Validate both seed playlists with `profile=region`. Stage all JSON and M3U files under a temporary directory inside the repository, parse them again, then replace the six destinations only after every check succeeds.

- [ ] **Step 4: Protect Wanger candidate refresh**

When refreshing source `wangerxiao`, run `select_curated_sites` with the candidate Spider reference before `write_candidate`. Missing/duplicate/invalid selected sites report `status: "failed"` and retain the previous candidate, stable files, policy, and automatic playlists.

- [ ] **Step 5: Implement CLI routes**

`compose` prints `{"composed": [...]}`. `publish-live` reads bytes from `--input`, maps `us` to `vendor/live/auto-us.m3u` and `health/live-us.json`, maps `cn` to `vendor/live/auto-cn.m3u` and `health/live-cn.json`, prints the report as JSON, and returns exit code 1 on `PlaylistError` without changing the destination.

- [ ] **Step 6: Extend regional verification**

For every requested region, load both stable JSON files, append `validate_config` and `validate_live_config` findings, and probe URLs from both documents when `--network` is set. Keep the existing `gitee-sync-pending` information finding for repository-owned mainland URLs until Gitee synchronization is complete.

- [ ] **Step 7: Run refresh and full tests**

Run: `python -m unittest tests.test_refresh -v`

Expected: PASS.

Run: `python -m unittest discover -s tests -v`

Expected: PASS with no stable or automatic-playlist mutation in the candidate-refresh test.

- [ ] **Step 8: Commit**

```powershell
git add hometv/refresh.py scripts/refresh.py tests/test_refresh.py
git commit -m "Add atomic HomeTV composition"
```

### Task 6: Documentation and Continuous Verification

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/refresh-candidates.yml`
- Create: `docs/verification/2026-08-16-curated-live-verification.md`

**Interfaces:**
- Documents the four permanent FongMi URLs and owner operations.
- Ensures pull requests run the complete unit suite and static verification.

- [ ] **Step 1: Update README with exact parent-facing settings**

Document these values verbatim:

```text
中国点播：https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json
中国直播：https://gitee.com/ds4213tv/hometv/raw/main/stable/live-cn.json
美国点播：https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json
美国直播：https://raw.githubusercontent.com/ds4213/hometv/main/stable/live-us.json
```

Also document `candidates`, `compose`, `verify`, `publish-live`, rollback by reverting content while preserving URLs, and the rule that candidate refresh cannot publish stable artifacts.

- [ ] **Step 2: Tighten the workflow**

Keep the existing daily candidate schedule. Before candidate refresh, run `python -m unittest discover -s tests -v`. After refresh, run `python scripts/refresh.py verify --regions us cn --probe-origin github-actions-us-approximation`. Keep staging limited to `candidates`, `vendor/manifest.json`, `vendor/nitan`, `vendor/wanger`, and `health`; explicitly exclude `stable` and `vendor/live/auto-*.m3u` from the scheduled commit.

- [ ] **Step 3: Run the repository verification commands**

```powershell
python -m unittest discover -s tests -v
python scripts/refresh.py verify --regions us cn
python -m json.tool stable/us.json > $null
python -m json.tool stable/cn.json > $null
python -m json.tool stable/live-us.json > $null
python -m json.tool stable/live-cn.json > $null
rg -n "github\.com|raw\.githubusercontent\.com" stable/cn.json stable/live-cn.json
```

Expected: all tests and JSON parsing pass; the final search returns no matches.

- [ ] **Step 4: Record verification evidence**

Record commit, UTC time, Python version, test count, site counts, live source names, playlist channel counts, Spider source/mirror MD5 and SHA-256, network probe origin, and clear limitations. State that US checks do not prove mainland media playback and Gitee checks do not prove every third-party stream.

- [ ] **Step 5: Commit**

```powershell
git add README.md .github/workflows/refresh-candidates.yml docs/verification/2026-08-16-curated-live-verification.md
git commit -m "Document curated HomeTV delivery"
```

### Task 7: Generate, Review, and Roll Out Phase 1

**Files:**
- Generate: `vendor/wanger/spider.jpg`
- Generate: `vendor/live/auto-cn.m3u`
- Generate: `vendor/live/auto-us.m3u`
- Generate: `stable/cn.json`
- Generate: `stable/us.json`
- Generate: `stable/live-cn.json`
- Generate: `stable/live-us.json`
- Generate: `health/cn.json`
- Generate: `health/us.json`

**Interfaces:**
- Publishes Phase 1 through GitHub review, then Gitee synchronization after approval.

- [ ] **Step 1: Refresh and compose from current candidates**

```powershell
python scripts/refresh.py candidates
python scripts/refresh.py compose
python scripts/refresh.py verify --regions us cn --network --probe-origin local-us-network
```

Expected: both candidates update; all six generated stable/vendor artifacts exist; US network checks are labeled as US-origin approximations.

- [ ] **Step 2: Inspect generated invariants**

```powershell
$us = Get-Content stable/us.json -Raw | ConvertFrom-Json
$cn = Get-Content stable/cn.json -Raw | ConvertFrom-Json
$liveUs = Get-Content stable/live-us.json -Raw | ConvertFrom-Json
$liveCn = Get-Content stable/live-cn.json -Raw | ConvertFrom-Json
($us.sites | Where-Object name -Like '🐮*').Count
($cn.sites | Where-Object name -Like '🐮*').Count
$liveUs.lives.name
$liveCn.lives.name
```

Expected: both counts are `35`; both LiveConfig files list the three expected names in the expected order.

- [ ] **Step 3: Commit generated artifacts**

```powershell
git add candidates vendor stable health docs/verification/2026-08-16-curated-live-verification.md
git commit -m "Publish curated Wang and live configs"
```

- [ ] **Step 4: Open a GitHub pull request and wait for checks**

Push the feature branch, open a draft PR against `main`, review the generated diff, and wait for the full test workflow. Do not merge the PR or push Gitee from an implementation subtask without the owner's explicit release instruction.

- [ ] **Step 5: After merge authorization, synchronize Gitee and verify all permanent URLs**

Fast-forward Gitee `main` to the reviewed GitHub `main`; never force-push. Verify HTTP 200, JSON/M3U content type or signature, and expected SHA-256 for all four permanent Vod/Live URLs plus the regional automatic playlist, Kimentanm playlist, and Wang Spider URLs. For mainland delivery, run the China Vod, China LiveConfig, `auto-cn.m3u`, and Wang Spider GET checks from one China Telecom node, one China Unicom node, and one China Mobile node; record carrier, city, timestamp, HTTP status, byte count, elapsed time, and SHA-256. Treat these as delivery checks, not proof that every media URL plays.

- [ ] **Step 6: Change only the N1 Live setting**

Set FongMi 5.6.1 Live to `https://gitee.com/ds4213tv/hometv/raw/main/stable/live-cn.json`. Keep Vod at `https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json`. Clear only FongMi cache, reload, verify 35 `🐮` sources, non-empty Live groups, one automatic channel, and one fallback channel. Roll back content by reverting the bad repository commit; do not change the permanent URLs.
