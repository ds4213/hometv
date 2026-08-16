# HomeTV GitHub Configurations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify stable US and mainland-China FongMi configuration artifacts on GitHub without modifying Gitee.

**Architecture:** A small Python standard-library package reads a declarative source registry, fetches complete upstream configurations into isolated candidate directories, mirrors approved static dependencies, and generates two stable regional variants. Scheduled refreshes update candidates and health reports only; promotion to `stable/` is an explicit command, and Gitee synchronization remains a later separately authorized operation.

**Tech Stack:** Python 3.12 standard library, `unittest`, JSON, GitHub Actions, Git/GitHub CLI.

## Global Constraints

- `stable/us.json` and `stable/cn.json` are the permanent FongMi entry paths.
- Never merge sites that require incompatible top-level Spider bundles.
- Never commit credentials, cookies, cloud-drive tokens, personal server keys, authenticated URLs, or probe secrets.
- Scheduled refreshes may update candidates, mirrored static dependencies, and health reports, but never stable files.
- A failed fetch retains the last known-good candidate and stable configuration.
- Gitee remains untouched until the owner explicitly authorizes synchronization.
- A GitHub-hosted mainland configuration can be structurally and externally validated before Gitee sync, but its final Gitee Raw URLs can only receive an end-to-end mainland test after that separately authorized sync.

---

### Task 1: Source Registry and Typed Loading

**Files:**
- Create: `sources/registry.json`
- Create: `hometv/__init__.py`
- Create: `hometv/registry.py`
- Create: `tests/test_registry.py`

**Interfaces:**
- Produces: `Source` dataclass with `id`, `name`, `url`, `regions`, `enabled`, `stable_regions`, and `disabled_reason` fields.
- Produces: `load_registry(path: Path) -> list[Source]`.

- [ ] **Step 1: Write registry loading tests**

```python
from pathlib import Path
import unittest

from hometv.registry import load_registry


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
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run: `python -m unittest tests.test_registry -v`

Expected: FAIL because `hometv.registry` does not exist.

- [ ] **Step 3: Create the source registry**

Use schema version 1 and these initial records:

```json
{
  "schema": 1,
  "sources": [
    {
      "id": "nitan-dm",
      "name": "泥潭弹幕版",
      "url": "https://nitan.ggff.net/config-dm.json",
      "regions": ["us", "cn"],
      "enabled": true,
      "stable_regions": ["us", "cn"]
    },
    {
      "id": "wangerxiao",
      "name": "王二小主力三代",
      "url": "https://9280.kstore.vip/aiwex.json",
      "regions": ["cn"],
      "enabled": true,
      "stable_regions": []
    },
    {
      "id": "aowu",
      "name": "嗷呜",
      "url": "https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config",
      "regions": ["cn"],
      "enabled": false,
      "stable_regions": [],
      "disabled_reason": "HTTP 404 on 2026-08-16"
    },
    {
      "id": "fantaiying",
      "name": "饭太硬",
      "url": "http://www.饭太硬.com/tv",
      "regions": ["cn"],
      "enabled": false,
      "stable_regions": [],
      "disabled_reason": "Connection timeout and no verified current JSON endpoint on 2026-08-16"
    },
    {
      "id": "ok",
      "name": "OK",
      "url": "http://ok213.top/tv",
      "regions": ["cn"],
      "enabled": false,
      "stable_regions": [],
      "disabled_reason": "DNS returned no usable address on 2026-08-16"
    }
  ]
}
```

- [ ] **Step 4: Implement strict typed loading**

`load_registry` must reject unsupported schema versions, duplicate IDs, unknown regions, enabled sources without URLs, and disabled sources without reasons. Return sources in registry order.

- [ ] **Step 5: Run registry tests**

Run: `python -m unittest tests.test_registry -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add sources/registry.json hometv/__init__.py hometv/registry.py tests/test_registry.py
git commit -m "Add HomeTV source registry"
```

### Task 2: Safe Fetching and Candidate Storage

**Files:**
- Create: `hometv/fetch.py`
- Create: `tests/test_fetch.py`
- Create: `candidates/.gitkeep`

**Interfaces:**
- Consumes: `Source` from `hometv.registry`.
- Produces: `FetchedConfig(source: Source, content: dict, raw: bytes, fetched_at: str, sha256: str)`.
- Produces: `fetch_config(source: Source, timeout: float = 20.0) -> FetchedConfig`.
- Produces: `write_candidate(fetched: FetchedConfig, root: Path) -> Path`.

- [ ] **Step 1: Write fetch validation tests**

Test with `unittest.mock.patch("urllib.request.urlopen")` that:

```python
self.assertRaises(FetchError, fetch_config, html_source)
self.assertRaises(FetchError, fetch_config, invalid_json_source)
self.assertEqual(fetch_config(json_source).content["sites"], [])
```

Also assert that a failed fetch does not replace an existing `candidates/<id>/upstream.json`.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_fetch -v`

Expected: FAIL because the fetch module does not exist.

- [ ] **Step 3: Implement fetching**

Use `urllib.request.Request` with a descriptive `User-Agent`, follow normal redirects, cap reads at 10 MiB, require HTTP 200, decode UTF-8 with BOM support, reject HTML signatures, parse a top-level JSON object, and compute SHA-256 over the raw bytes.

- [ ] **Step 4: Implement atomic candidate writes**

Write `upstream.json.tmp`, parse it again, then replace `upstream.json` with `Path.replace`. Write `metadata.json` only after the configuration replacement succeeds.

- [ ] **Step 5: Run fetch tests**

Run: `python -m unittest tests.test_fetch -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add hometv/fetch.py tests/test_fetch.py candidates/.gitkeep
git commit -m "Add safe candidate fetching"
```

### Task 3: Static Dependency Mirroring and Regional Generation

**Files:**
- Create: `hometv/build.py`
- Create: `tests/test_build.py`
- Create: `vendor/.gitkeep`
- Create: `stable/.gitkeep`

**Interfaces:**
- Consumes: parsed candidate JSON.
- Produces: `build_us(config: dict) -> dict`.
- Produces: `build_cn(config: dict, gitee_base: str) -> BuildResult`.
- Produces: `BuildResult(config: dict, mirrors: tuple[MirrorRequest, ...])`.
- Produces: `MirrorRequest(source_url: str, repository_path: str)`.

- [ ] **Step 1: Write regional build tests**

Use a fixture containing the current Nitan Spider, Douban extension, Python site, GitHub live lists, wallpaper, and overseas DoH entries. Assert:

```python
us = build_us(fixture)
self.assertEqual(us["spider"], fixture["spider"])

cn = build_cn(fixture, "https://gitee.com/ds4213tv/hometv/raw/main")
self.assertEqual(
    cn.config["spider"],
    "https://gitee.com/ds4213tv/hometv/raw/main/vendor/nitan/awdm.png",
)
self.assertNotIn("raw.githubusercontent.com", json.dumps(cn.config))
self.assertNotIn("github.com", json.dumps(cn.config))
self.assertEqual([item["name"] for item in cn.config["doh"]], ["AliDNS", "DNSPod"])
```

Assert that mirror requests include `awdm.png`, `db.aowu`, `py_jinpai.py`, Kimentanm, Migu, YanG Gather, and YanG Sport.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_build -v`

Expected: FAIL because `hometv.build` does not exist.

- [ ] **Step 3: Implement US generation**

Return a deep copy of the validated upstream configuration without mutating the candidate.

- [ ] **Step 4: Implement mainland generation**

Rewrite approved static dependencies to these repository paths:

```text
vendor/nitan/awdm.png
vendor/nitan/db.aowu
vendor/nitan/py/py_jinpai.py
vendor/live/kimentanm.m3u
vendor/live/migu.txt
vendor/live/yang-gather.m3u
vendor/live/yang-sport.m3u
```

Replace the mainland DoH list with:

```json
[
  {
    "name": "AliDNS",
    "url": "https://dns.alidns.com/dns-query",
    "ips": ["223.5.5.5", "223.6.6.6"]
  },
  {
    "name": "DNSPod",
    "url": "https://doh.pub/dns-query",
    "ips": ["1.12.12.12", "120.53.53.53"]
  }
]
```

Set `wallpaper` to an empty string to remove a nonessential external dependency. Preserve dynamic `vod.catvod.ggff.net` APIs for probing because they cannot be converted into static repository files.

- [ ] **Step 5: Implement mirrored downloads**

Download each `MirrorRequest` atomically, cap individual files at 25 MiB, reject HTML, and retain the previous file on failure. Record source URL, byte count, and SHA-256 in `vendor/manifest.json`.

- [ ] **Step 6: Run build tests**

Run: `python -m unittest tests.test_build -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add hometv/build.py tests/test_build.py vendor/.gitkeep stable/.gitkeep
git commit -m "Generate regional FongMi configurations"
```

### Task 4: Validation and Honest Health Reports

**Files:**
- Create: `hometv/validate.py`
- Create: `tests/test_validate.py`
- Create: `health/.gitkeep`

**Interfaces:**
- Produces: `validate_config(config: dict, region: str) -> list[Finding]`.
- Produces: `probe_http(url: str, timeout: float = 15.0) -> ProbeResult`.
- Produces: `write_health_report(region: str, findings: list[Finding], probes: list[ProbeResult], path: Path, probe_origin: str) -> None`.

- [ ] **Step 1: Write validation tests**

Assert that validation reports malformed `sites`/`lives`, duplicate site keys, HTTP cleartext endpoints as warnings, GitHub URLs in the mainland configuration as errors, and unavailable dynamic APIs as errors without modifying stable files.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_validate -v`

Expected: FAIL because the validation module does not exist.

- [ ] **Step 3: Implement static validation**

Classify findings as `error`, `warning`, or `info`. Mainland GitHub dependencies are errors. Cleartext HTTP, nonessential wallpaper endpoints, and disabled search capabilities are warnings or information.

- [ ] **Step 4: Implement HTTP and playlist probes**

For JSON/assets, require a successful status and non-HTML body. For M3U/M3U8, parse the first playable URL and request its first media resource with a byte range. Never log query-string credentials.

- [ ] **Step 5: Implement health reports**

Include `generated_at`, `region`, `probe_origin`, overall status, findings, sanitized probe targets, status codes, elapsed milliseconds, and SHA-256 where applicable. A US GitHub Actions run must use `probe_origin: "github-actions-us-approximation"`; it must never claim to be a mainland measurement.

- [ ] **Step 6: Run validation tests**

Run: `python -m unittest tests.test_validate -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add hometv/validate.py tests/test_validate.py health/.gitkeep
git commit -m "Add configuration health validation"
```

### Task 5: Refresh CLI and GitHub Automation

**Files:**
- Create: `scripts/refresh.py`
- Create: `tests/test_refresh.py`
- Create: `.github/workflows/refresh-candidates.yml`
- Create: `README.md`

**Interfaces:**
- Consumes all earlier package functions.
- Produces CLI commands:
  - `python scripts/refresh.py candidates`
  - `python scripts/refresh.py promote --source nitan-dm --regions us cn`
  - `python scripts/refresh.py verify --regions us cn`

- [ ] **Step 1: Write CLI behavior tests**

Use temporary directories and mocked network functions. Assert that `candidates` never writes under `stable/`, `promote` requires a healthy candidate, and failed promotion leaves existing stable files unchanged.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_refresh -v`

Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement the CLI**

`candidates` processes enabled registry entries in order and continues after individual failures. `promote` builds requested regional variants in a temporary directory, validates every output and mirror, and atomically replaces stable files only when no errors remain. `verify` performs read-only validation and probes.

- [ ] **Step 4: Add scheduled candidate refresh**

The workflow runs at 03:17 UTC daily and by manual dispatch. It checks out `main`, runs all tests, runs `candidates`, and commits only changes below `candidates/`, `vendor/`, and `health/`. It must not stage `stable/`.

- [ ] **Step 5: Document owner workflows**

README instructions must cover adding one registry record, reviewing health output, explicit promotion, rollback with Git history, GitHub stable URLs, and the rule that Gitee sync needs separate authorization.

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/refresh.py tests/test_refresh.py .github/workflows/refresh-candidates.yml README.md
git commit -m "Automate candidate refreshes"
```

### Task 6: Generate Initial Artifacts and Verify GitHub Delivery

**Files:**
- Generate: `candidates/nitan-dm/upstream.json`
- Generate: `candidates/nitan-dm/metadata.json`
- Generate: `candidates/wangerxiao/upstream.json`
- Generate: `candidates/wangerxiao/metadata.json`
- Generate: `vendor/nitan/**`
- Generate: `vendor/live/**`
- Generate: `vendor/manifest.json`
- Generate: `stable/us.json`
- Generate: `stable/cn.json`
- Generate: `health/us.json`
- Generate: `health/cn.json`
- Create: `docs/verification/2026-08-16-github-verification.md`

**Interfaces:**
- Publishes stable GitHub paths only; no Gitee mutation.

- [ ] **Step 1: Refresh enabled candidates**

Run: `python scripts/refresh.py candidates`

Expected: Nitan and Wangerxiao candidate JSON files exist; disabled Aowu, Fantaiying, and OK records are reported but not fetched.

- [ ] **Step 2: Promote Nitan to both regional stable paths**

Run: `python scripts/refresh.py promote --source nitan-dm --regions us cn`

Expected: `stable/us.json` retains original US dependencies; `stable/cn.json` references future Gitee Raw paths for mirrored static assets.

- [ ] **Step 3: Run local verification**

```powershell
python -m unittest discover -s tests -v
python scripts/refresh.py verify --regions us cn
python -m json.tool stable/us.json > $null
python -m json.tool stable/cn.json > $null
rg -n "github\.com|raw\.githubusercontent\.com" stable/cn.json
```

Expected: tests and JSON parsing pass; the final `rg` command returns no matches.

- [ ] **Step 4: Perform independent network checks**

Check the GitHub Raw US configuration and vendor assets from the current overseas network. Use a mainland multi-node HTTP service for the dynamic Nitan API host, Spider source before rewrite, and representative live sources. Record exact timestamps, node types, success counts, and limitations in the verification document. Do not claim final Gitee Raw success because Gitee has not been authorized or populated.

- [ ] **Step 5: Commit generated artifacts and verification evidence**

```powershell
git add candidates vendor stable health docs/verification/2026-08-16-github-verification.md
git commit -m "Publish verified HomeTV GitHub configurations"
```

- [ ] **Step 6: Push through a review branch**

Push the implementation branch, open a draft pull request to `main`, verify GitHub Actions, then report the PR and exact remaining mainland/Gitee validation boundary to the owner. Do not merge or synchronize Gitee without the owner's next instruction.
