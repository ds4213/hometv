# Five-Source Candidate Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manage Nitan, Wang, Aowu, Fantaiying, and OK through reviewed endpoints, isolated last-known-good candidates, and source health reports without automatically changing the parents' stable FongMi configuration.

**Architecture:** A schema-v2 registry contains only reviewed runtime endpoints; untrusted alternate addresses live in a non-runtime discovery catalog. A guarded endpoint fetcher produces per-source outcomes, atomically preserves candidates and health, and a reviewed promotion manifest is the only path from candidate data into the existing six-output atomic composer.

**Tech Stack:** Python 3.12 standard library (`dataclasses`, `urllib`, `ipaddress`, `socket`, `json`, `hashlib`), `unittest`, JSON configuration, GitHub Actions.

## Global Constraints

- Manage exactly five source IDs: `nitan-dm`, `wangerxiao`, `aowu`, `fantaiying`, and `ok`.
- The current US and China stable Vod files remain at 49 sites until a separate promotion is reviewed and approved.
- Candidate refresh may write only candidates, `health/sources`, manifest data, and reviewed dependency mirrors; it may not change `stable/**` or `vendor/live/auto-*.m3u`.
- All five sources remain monitored even when their health status is `unavailable`; administrative disablement is separate from reachability.
- Runtime fetching uses only reviewed registry endpoints. `sources/discovered-endpoints.json` is never read by the scheduled refresher.
- A failed refresh preserves the previous candidate and candidate metadata byte-for-byte.
- A recovered backup source updates a candidate only; stable promotion is manual and requires an allowlist plus pull-request review.
- Repository-owned US dependencies use GitHub Raw; repository-owned China dependencies use Gitee. China stable documents may not contain GitHub repository hosts.
- US probes are labeled as US-origin approximations and do not prove mainland playback.
- Errors and health data must not expose URL userinfo, query values, tokens, cookies, or authorization data.
- Do not perform Docker/NAS work, Gitee synchronization, N1 changes, or persistent Gitee automation in this plan.

---

## File Structure

- Modify `hometv/registry.py`: schema-v2 endpoint and source models plus discovery-catalog validation.
- Modify `sources/registry.json`: five monitored sources and reviewed primary endpoints.
- Create `sources/discovered-endpoints.json`: non-runtime alternate-address inventory and provenance.
- Modify `hometv/fetch.py`: one-endpoint safe fetch, redirect policy, candidate shape validation, and reproducible snapshot writes.
- Create `hometv/source_candidates.py`: ordered fallback, outcome/attempt models, atomic health writes, and read-only discovery probes.
- Modify `hometv/refresh.py`: five-source orchestration, source-specific gates, nonblocking backup failures, and stable-mutation protection.
- Modify `scripts/refresh.py`: candidate probe origin, read-only `probe-endpoint`, and blocking exit semantics.
- Modify `.github/workflows/refresh-candidates.yml`: source-health staging and explicit stable-output guard.
- Modify `hometv/curation.py`: reviewed promotion-manifest model and validation.
- Modify `hometv/build.py`: compose any manifest-approved curated source while preserving source-specific Spider isolation.
- Create `sources/promotions.json`: current production manifest containing Wang only.
- Modify `README.md`: five-source operations and manual promotion boundary.
- Create `docs/verification/2026-08-16-five-source-health.md`: live evidence and limitations.
- Extend `tests/test_registry.py`, `tests/test_fetch.py`, `tests/test_refresh.py`, `tests/test_build.py`, and `tests/test_curation.py`; create `tests/test_source_candidates.py`.

### Task 1: Schema-V2 Reviewed Endpoint Registry

**Files:**
- Modify: `hometv/registry.py`
- Modify: `sources/registry.json`
- Create: `sources/discovered-endpoints.json`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Produces: `Endpoint(url: str, role: str, provenance: str, reviewed_at: str, notes: str = "")`.
- Produces: `Source(..., endpoints: tuple[Endpoint, ...], candidate_mode: str, promotion: str, prefix: str, ...)` with compatibility property `url -> endpoints[0].url`.
- Produces: `DiscoveredEndpoint(source_id: str, url: str, provenance: str, discovered_at: str, status: str, last_checked_at: str | None, evidence: str)`.
- Produces: `load_registry(path: Path) -> list[Source]` and `load_discovered_endpoints(path: Path, source_ids: set[str]) -> list[DiscoveredEndpoint]`.

- [ ] **Step 1: Add failing schema-v2 production and validation tests**

Add tests that require the exact five IDs, all five `enabled=True`, ordered primary endpoints, manual/quarantine policy, stable-region truth, exact prefixes, and a discovery catalog that is separate from runtime endpoints:

```python
def test_production_registry_manages_exact_five_sources():
    sources = load_registry(Path("sources/registry.json"))
    self.assertEqual(
        [source.id for source in sources],
        ["nitan-dm", "wangerxiao", "aowu", "fantaiying", "ok"],
    )
    self.assertTrue(all(source.enabled for source in sources))
    self.assertTrue(all(source.candidate_mode == "quarantine" for source in sources))
    self.assertTrue(all(source.promotion == "manual" for source in sources))
    self.assertEqual(next(s for s in sources if s.id == "wangerxiao").prefix, "🐮")
    self.assertEqual(next(s for s in sources if s.id == "aowu").stable_regions, ())

def test_discovered_urls_are_not_runtime_endpoints():
    sources = load_registry(Path("sources/registry.json"))
    runtime_urls = {endpoint.url for source in sources for endpoint in source.endpoints}
    discovered = load_discovered_endpoints(
        Path("sources/discovered-endpoints.json"), {source.id for source in sources}
    )
    self.assertIn("http://itv666.cc/aowu/config.webp", {item.url for item in discovered})
    self.assertNotIn("http://itv666.cc/aowu/config.webp", runtime_urls)
```

Add table-driven invalid-record tests for unknown fields, duplicate IDs/URLs, an alternate before the primary, missing provenance/review time, invalid ISO timestamps, URL userinfo, fragments, sensitive query keys, unsupported `candidate_mode`/`promotion`, `stable_regions` outside `regions`, disabled sources without an administrative reason, discovery records referencing unknown source IDs, and discovery statuses outside `unverified|unavailable|promoted`.

- [ ] **Step 2: Run the registry tests and verify RED**

Run: `python -m unittest tests.test_registry -v`

Expected: FAIL because schema 2 and the endpoint/discovery models do not exist.

- [ ] **Step 3: Implement exact dataclasses and strict loaders**

Use these public shapes:

```python
@dataclass(frozen=True)
class Endpoint:
    url: str
    role: str
    provenance: str
    reviewed_at: str
    notes: str = ""

@dataclass(frozen=True)
class Source:
    id: str
    name: str
    regions: tuple[str, ...]
    enabled: bool
    stable_regions: tuple[str, ...]
    endpoints: tuple[Endpoint, ...]
    candidate_mode: str
    promotion: str
    prefix: str
    disabled_reason: str = ""

    @property
    def url(self) -> str:
        return self.endpoints[0].url

@dataclass(frozen=True)
class DiscoveredEndpoint:
    source_id: str
    url: str
    provenance: str
    discovered_at: str
    status: str
    last_checked_at: str | None
    evidence: str
```

Require exact allowed field sets instead of silently accepting misspellings. Parse timestamps with `datetime.fromisoformat(value.replace("Z", "+00:00"))` and require timezone information. Reject URL userinfo/fragments and query keys matching `token|key|secret|password|passwd|auth|cookie|session` case-insensitively.

- [ ] **Step 4: Write the exact production JSON files**

Set schema 2, enable all five for monitoring, use both regions for all five, set Nitan and Wang `stable_regions` to `us,cn`, and leave the other three empty. Use prefixes `""`, `🐮`, `🐺`, `🍚`, and `🆗` respectively. Runtime registry endpoints initially contain only these reviewed primary addresses, in source order:

```text
nitan-dm:   https://nitan.ggff.net/config-dm.json
wangerxiao: https://9280.kstore.vip/aiwex.json
aowu:       https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config
fantaiying: http://www.饭太硬.com/tv
ok:         http://ok213.top/tv
```

Give every primary endpoint `role: "primary"`, a non-empty provenance, and a timezone-aware `reviewed_at`. Preserve these discovered addresses in the non-runtime catalog:

```json
{
  "schema": 1,
  "endpoints": [
    {
      "source_id": "aowu",
      "url": "http://itv666.cc/aowu/config.webp",
      "provenance": "public interface reference reviewed 2026-08-16",
      "discovered_at": "2026-08-16T00:00:00+00:00",
      "status": "unverified",
      "last_checked_at": null,
      "evidence": ""
    },
    {
      "source_id": "fantaiying",
      "url": "http://www.饭太硬.net/tv",
      "provenance": "public interface reference reviewed 2026-08-16",
      "discovered_at": "2026-08-16T00:00:00+00:00",
      "status": "unverified",
      "last_checked_at": null,
      "evidence": ""
    },
    {
      "source_id": "fantaiying",
      "url": "http://www.饭太硬.top/tv/",
      "provenance": "public interface reference reviewed 2026-08-16",
      "discovered_at": "2026-08-16T00:00:00+00:00",
      "status": "unverified",
      "last_checked_at": null,
      "evidence": ""
    }
  ]
}
```

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
python -m unittest tests.test_registry tests.test_fetch tests.test_refresh -v
python -m unittest discover -s tests -v
```

Expected: PASS after adapting existing test fixtures to construct `Source(endpoints=(Endpoint(...),))`.

- [ ] **Step 6: Commit**

```powershell
git add hometv/registry.py sources/registry.json sources/discovered-endpoints.json tests/test_registry.py tests/test_fetch.py tests/test_refresh.py
git commit -m "Add reviewed five-source endpoint registry"
```

### Task 2: Guarded Endpoint Fetching, Candidate Snapshots, and Source Health

**Files:**
- Modify: `hometv/fetch.py`
- Create: `hometv/source_candidates.py`
- Modify: `tests/test_fetch.py`
- Create: `tests/test_source_candidates.py`

**Interfaces:**
- Consumes: `Endpoint`, `Source` from Task 1.
- Changes: `FetchedConfig` adds `endpoint: Endpoint` and `http_status: int`.
- Produces: `EndpointAttempt(endpoint_url: str, safe_url: str, ok: bool, http_status: int | None, elapsed_ms: int, error: str)`.
- Produces: `CandidateOutcome(source: Source, status: str, selected_endpoint: str, fetched: FetchedConfig | None, attempts: tuple[EndpointAttempt, ...], warnings: tuple[str, ...])`.
- Produces: `fetch_config(source: Source, endpoint: Endpoint | None = None, timeout: float = 20.0, opener=None, resolver=socket.getaddrinfo) -> FetchedConfig`.
- Produces: `fetch_candidate(source: Source, fetcher: Callable = fetch_config, clock: Callable = time.perf_counter) -> CandidateOutcome`.
- Produces: `write_candidate_snapshot(outcome: CandidateOutcome, root: Path) -> Path`.
- Produces: `write_source_health(outcome: CandidateOutcome, root: Path, probe_origin: str, now: Callable = ...) -> Path`.
- Produces: `probe_discovered_endpoint(source: Source, url: str, fetcher: Callable = fetch_config) -> dict[str, object]` with no filesystem writes.

- [ ] **Step 1: Add failing URL, redirect, content, and fallback tests**

Cover public IPv4/IPv6 and IDN hosts plus these exact rejection classes:

```python
def test_primary_failure_then_reviewed_alternate_success(self):
    calls = []
    def fake_fetch(source, endpoint):
        calls.append(endpoint.url)
        if endpoint.role == "primary":
            raise FetchError("primary unavailable", http_status=503)
        return fetched(source, endpoint, {"sites": [{"key": "ok", "api": "csp_X"}]})
    outcome = fetch_candidate(source_with_two_endpoints(), fetcher=fake_fetch)
    self.assertEqual(calls, ["https://primary.example/config", "https://alt.example/config"])
    self.assertEqual(outcome.status, "usable")
    self.assertEqual(outcome.selected_endpoint, "https://alt.example/config")

def test_all_endpoint_failures_preserve_last_good_candidate_and_metadata(self):
    originals = seed_candidate_pair(self.root)
    outcome = fetch_candidate(source_with_two_endpoints(), fetcher=always_fail)
    with self.assertRaisesRegex(FetchError, "no usable endpoint"):
        write_candidate_snapshot(outcome, self.root / "candidates")
    self.assertEqual(candidate_pair(self.root), originals)
```

Also test literal/private and DNS-resolved private addresses, localhost/`.local`/metadata hostnames, URL userinfo, sensitive queries, a public URL redirecting private, redirect loops/excess count, HTML, empty, oversized, invalid UTF-8/JSON, non-object JSON, empty/missing sites, duplicate/blank keys, malformed HTTP-like Spider/Jar/API/ext references, and response metadata sanitization.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m unittest tests.test_fetch tests.test_source_candidates -v`

Expected: FAIL because endpoint outcomes and source health do not exist.

- [ ] **Step 3: Implement public-address and redirect policy**

Use `urllib.parse.urlsplit`, `ipaddress.ip_address`, and an injected resolver. Require every resolved address to satisfy `ip.is_global`; explicitly deny `localhost`, `.localhost`, `.local`, and known metadata hosts. Install a custom `HTTPRedirectHandler` whose `redirect_request` validates each target before following it and caps redirects at five. Construct requests without `shell` and keep the existing HomeTV User-Agent.

```python
def validate_public_url(url: str, resolver=socket.getaddrinfo) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise FetchError("endpoint must be public HTTP(S)")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise FetchError("endpoint contains forbidden URL components")
    hostname = parsed.hostname.rstrip(".").casefold()
    denied = {
        "localhost",
        "metadata",
        "metadata.google.internal",
        "instance-data",
        "instance-data.ec2.internal",
    }
    if hostname in denied or hostname.endswith((".localhost", ".local")):
        raise FetchError("endpoint hostname is forbidden")
    addresses = {item[4][0] for item in resolver(hostname, parsed.port or 0)}
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise FetchError("endpoint resolves to a non-public address")
    return url

class PolicyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl, self.resolver)
        self.redirect_count += 1
        if self.redirect_count > 5:
            raise FetchError("too many redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)
```

Extend `FetchError`:

```python
class FetchError(RuntimeError):
    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status
```

Sanitize errors before storing them; retain only scheme/host/path for URLs and replace query/userinfo with `[redacted]`.

- [ ] **Step 4: Implement strict candidate shape validation**

Require `sites` to be a non-empty list of objects with unique, non-empty string keys. Require a site's `api` to be a non-empty string when present. Accept JSON-compatible `ext` values, but validate every string that begins with `http:`, `https:`, `http:/`, or `https:/`. Validate top-level `spider` and per-site `jar` HTTP references, including optional `;md5;<32 hex>` suffixes. Return warnings for non-HTTP local dependency forms rather than treating them as promotion-ready.

```python
def validate_candidate_config(content: dict) -> tuple[str, ...]:
    sites = content.get("sites")
    if not isinstance(sites, list) or not sites:
        raise FetchError("configuration sites must be a non-empty list")
    seen: set[str] = set()
    warnings: list[str] = []
    for index, site in enumerate(sites):
        if not isinstance(site, dict):
            raise FetchError(f"site {index} must be an object")
        key = site.get("key")
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise FetchError(f"site {index} has an invalid or duplicate key")
        seen.add(key)
        validate_dependency_fields(site, warnings, f"$.sites[{index}]")
    validate_dependency_fields(content, warnings, "$")
    return tuple(warnings)
```

- [ ] **Step 5: Implement ordered outcomes and atomic persistence**

`fetch_candidate` tries reviewed endpoints in order, records sanitized attempts, returns `unavailable` only after all fail, and never reads the discovery catalog. `write_candidate_snapshot` requires `outcome.fetched`, serializes candidate and metadata fully before replacement, writes unique same-directory temporary files, and rolls back both files if either replacement fails. Metadata includes selected endpoint, source-response bytes/hash, canonical candidate bytes/hash, site count, and warnings.

`write_source_health` writes `health/sources/<id>.json` atomically with status, probe origin, selected endpoint, attempts, warnings, and candidate facts. It may write health for `unavailable` outcomes but never changes candidate files.

```python
def fetch_candidate(source, fetcher=fetch_config, clock=time.perf_counter):
    attempts = []
    for endpoint in source.endpoints:
        started = clock()
        try:
            fetched = fetcher(source, endpoint)
            warnings = validate_candidate_config(fetched.content)
            attempts.append(success_attempt(endpoint, fetched, started, clock()))
            status = "degraded" if warnings else "usable"
            return CandidateOutcome(source, status, endpoint.url, fetched, tuple(attempts), warnings)
        except FetchError as exc:
            attempts.append(failed_attempt(endpoint, exc, started, clock()))
    return CandidateOutcome(source, "unavailable", "", None, tuple(attempts), ())
```

Writers serialize all bytes before the first replacement, use unique
same-directory temporary paths, save existing destination bytes, and restore
those bytes if any replacement raises.

- [ ] **Step 6: Implement read-only discovery probing**

`probe_discovered_endpoint` accepts only a URL already selected by the caller, fetches and validates it with the same policy, returns a JSON-serializable evidence dictionary, and does not call either writer. Include `source`, sanitized `url`, `checked_at`, `status`, response/candidate hashes, site count, warnings, and sanitized error.

- [ ] **Step 7: Run focused and full tests**

Run:

```powershell
python -m unittest tests.test_fetch tests.test_source_candidates -v
python -m unittest discover -s tests -v
python -m py_compile hometv/fetch.py hometv/source_candidates.py
```

Expected: PASS, including rollback injection on the first and second candidate-pair replacements and health-write failure.

- [ ] **Step 8: Commit**

```powershell
git add hometv/fetch.py hometv/source_candidates.py tests/test_fetch.py tests/test_source_candidates.py
git commit -m "Add guarded source candidate fetching"
```

### Task 3: Five-Source Refresh Orchestration and CLI

**Files:**
- Modify: `hometv/refresh.py`
- Modify: `scripts/refresh.py`
- Modify: `.github/workflows/refresh-candidates.yml`
- Modify: `tests/test_refresh.py`

**Interfaces:**
- Consumes: Task 2 candidate outcomes and writers.
- Changes: `refresh_candidates(root: Path, endpoint_fetcher: Callable = fetch_config, mirror_func: Callable = mirror_files, probe_origin: str = "local-us-network") -> list[dict]`.
- Produces CLI: `python scripts/refresh.py candidates --probe-origin <label>`.
- Produces CLI: `python scripts/refresh.py probe-endpoint --source <id> --url <catalog-url>`; it refuses URLs not present for that source in `sources/discovered-endpoints.json`.

- [ ] **Step 1: Add failing five-source isolation and exit-policy tests**

```python
def test_refresh_attempts_all_five_and_backup_failure_is_nonblocking(self):
    attempted = []
    def endpoint_fetcher(source, endpoint):
        attempted.append(source.id)
        if source.id in {"aowu", "fantaiying", "ok"}:
            raise FetchError("offline")
        return valid_fetched(source, endpoint)
    results = refresh_candidates(self.root, endpoint_fetcher=endpoint_fetcher)
    self.assertEqual(attempted, ["nitan-dm", "wangerxiao", "aowu", "fantaiying", "ok"])
    self.assertFalse(any(item["blocking"] for item in results if item["source"] in {"aowu", "fantaiying", "ok"}))
    self.assertEqual(load_health(self.root, "aowu")["status"], "unavailable")

def test_candidate_refresh_cannot_change_release_paths(self):
    before = snapshot_release_paths(self.root)
    refresh_candidates(self.root, endpoint_fetcher=fixture_fetcher)
    self.assertEqual(snapshot_release_paths(self.root), before)
```

Add tests for stable Nitan/Wang failure marked `blocking=True`, one source failure not stopping later sources, Wang exact-35 failure preserving its candidate, structurally valid backup candidate saved as `usable`, dependency warning saved as `degraded`, health write on every source, and discovery probe rejection when the URL/source pair is absent from the catalog.

- [ ] **Step 2: Run refresh/CLI tests and verify RED**

Run: `python -m unittest tests.test_refresh -v`

Expected: FAIL because refresh has no endpoint-outcome, source-health, or
catalog-probe semantics yet.

- [ ] **Step 3: Refactor refresh orchestration around outcomes**

For every enabled registry source, call `fetch_candidate` with the injected endpoint fetcher. Apply these source-specific gates before replacing a candidate:

- Wang: existing exact 35-key policy plus MD5 Spider validation and hash-checked Spider mirror.
- Nitan: existing regional dependency build/mirror checks.
- Aowu/Fantaiying/OK: generic candidate validation only; unresolved or non-mirrorable dependencies produce `degraded` warnings and cannot affect stable output.

Write the candidate only for `usable|degraded`, then write source health. If a gate converts a fetched result to `unavailable`, preserve the previous candidate. Continue to later sources after any source-level failure.

```python
for source in load_registry(root / "sources/registry.json"):
    outcome = fetch_candidate(
        source,
        fetcher=lambda current, endpoint: endpoint_fetcher(current, endpoint),
    )
    outcome = apply_source_gate(root, outcome, mirror_func)
    candidate_path = None
    if outcome.status in {"usable", "degraded"}:
        candidate_path = write_candidate_snapshot(outcome, root / "candidates")
    write_source_health(outcome, root / "health" / "sources", probe_origin)
    results.append(result_payload(source, outcome, candidate_path))
```

Each returned dictionary contains `source`, `status`, `blocking`, `selected_endpoint`, `candidate_path`, `candidate_sha256`, `warnings`, and `message`. `blocking` is true only when an unavailable source currently has non-empty `stable_regions` or when candidate/health persistence itself fails.

- [ ] **Step 4: Add CLI behavior and safe discovery probe**

Add `--probe-origin` to `candidates`. Exit 1 only when a result is blocking; unavailable quarantined backups still produce exit 0 and honest health.

Add:

```text
probe-endpoint --source aowu --url http://itv666.cc/aowu/config.webp
```

The command must load the catalog, require an exact source/URL match, call the read-only probe, print JSON, and return 0 for `usable|degraded`, 1 for `unavailable`. It must not update registry, discovery, candidate, health, stable, or Git state.

- [ ] **Step 5: Tighten the workflow allowlist**

Run tests before refresh. Invoke candidates with `--probe-origin github-actions-us-approximation`. Stage `candidates`, `health/sources`, `vendor/manifest.json`, `vendor/nitan`, and `vendor/wanger`. After staging, reject any cached path outside this exact allowlist as well as the existing explicit `stable/**` and `vendor/live/auto-*.m3u` guards. PRs continue to run tests/static verification only and never refresh or push.

- [ ] **Step 6: Run focused and full tests**

Run:

```powershell
python -m unittest tests.test_refresh tests.test_registry tests.test_source_candidates -v
python -m unittest discover -s tests -v
python -m py_compile hometv/refresh.py scripts/refresh.py
```

Expected: PASS. A fixture with 49-site stable configs must remain byte-identical after all five candidate statuses are processed.

- [ ] **Step 7: Commit**

```powershell
git add hometv/refresh.py scripts/refresh.py .github/workflows/refresh-candidates.yml tests/test_refresh.py
git commit -m "Refresh all five sources without promotion"
```

### Task 4: Reviewed Promotion Manifest and Generic Curated Composition

**Files:**
- Modify: `hometv/curation.py`
- Modify: `hometv/build.py`
- Modify: `hometv/refresh.py`
- Modify: `scripts/refresh.py`
- Create: `sources/promotions.json`
- Modify: `tests/test_curation.py`
- Modify: `tests/test_build.py`
- Modify: `tests/test_refresh.py`

**Interfaces:**
- Produces: `PromotionEntry(source_id: str, policy_path: str, repository_path: str)`.
- Produces: `PromotionManifest(base_source_id: str, entries: tuple[PromotionEntry, ...])`.
- Produces: `load_promotion_manifest(root: Path, path: Path) -> PromotionManifest`.
- Changes: `build_curated_vod(base: dict, curated: tuple[tuple[dict, CuratedSource, str], ...], region: str, github_base: str, gitee_base: str) -> BuildResult`.
- Produces: `analyze_promotion(root: Path, source_id: str, policy_path: Path) -> dict[str, object]` with no stable writes.
- Removes the unsafe direct-write meaning of CLI `promote`; stable promotion occurs only by reviewed manifest/policy changes followed by `compose`.

- [ ] **Step 1: Add failing manifest, collision, and no-direct-promotion tests**

```python
def test_production_manifest_promotes_only_current_wang_policy(self):
    manifest = load_promotion_manifest(Path.cwd(), Path("sources/promotions.json"))
    self.assertEqual(manifest.base_source_id, "nitan-dm")
    self.assertEqual([entry.source_id for entry in manifest.entries], ["wangerxiao"])

def test_promotion_report_does_not_write_stable(self):
    before = generated_snapshot(self.root)
    report = analyze_promotion(self.root, "aowu", self.root / "sources/curation/aowu.json")
    self.assertIn("eligible", report)
    self.assertEqual(generated_snapshot(self.root), before)
```

Add tests for unsafe/escaping policy paths, duplicate source IDs/repository paths, manifest source absent from registry, prefix mismatch against registry, missing/duplicate allowlist keys, key collision with base or an earlier curated source, invalid/non-MD5 Spider, conflicting mirror destinations, and a future Aowu fixture composing only after it is present in both a reviewed policy and the manifest.

- [ ] **Step 2: Run curation/build/refresh tests and verify RED**

Run: `python -m unittest tests.test_curation tests.test_build tests.test_refresh -v`

Expected: FAIL because composition is hard-coded to Wang and direct `promote` writes stable files.

- [ ] **Step 3: Implement strict promotion-manifest loading**

Use schema 1:

```json
{
  "schema": 1,
  "base_source_id": "nitan-dm",
  "sources": [
    {
      "source_id": "wangerxiao",
      "policy_path": "sources/wanger-curated.json",
      "repository_path": "vendor/wanger/spider.jpg"
    }
  ]
}
```

Resolve policy paths under the repository root with `Path.resolve()` and reject traversal. Require unique source IDs and repository paths. Require the policy source ID and prefix to match the registry source. A manifest entry is the explicit reviewed activation gate.

```python
def load_promotion_manifest(root: Path, path: Path) -> PromotionManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require_exact_fields(payload, {"schema", "base_source_id", "sources"})
    entries = tuple(parse_promotion_entry(root, item) for item in payload["sources"])
    if len({item.source_id for item in entries}) != len(entries):
        raise CurationError("duplicate promoted source")
    if len({item.repository_path for item in entries}) != len(entries):
        raise CurationError("duplicate promotion repository path")
    return PromotionManifest(payload["base_source_id"], entries)
```

- [ ] **Step 4: Generalize curated regional composition**

Build the base source first, then iterate manifest entries in stored order. For each entry, parse its candidate Spider `URL;md5;<digest>`, construct a region-owned Jar URL from the entry's repository path, select allowlisted sites, reject collisions, append sites, and add exactly one hash-checked mirror request. A source with an incompatible Spider or global-field requirement fails composition and remains quarantined until a source-specific adapter is reviewed.

The production manifest contains Wang only, so regenerated stable JSON must be semantically identical to the current 49-site output.

```python
result = BuildResult(config=regional_base(base, region), mirrors=base_mirrors)
for candidate, policy, repository_path in curated:
    source_url, _algorithm, digest = parse_spider_reference(candidate.get("spider"))
    owned_base = github_base if region == "us" else gitee_base
    jar = f"{owned_base.rstrip('/')}/{repository_path};md5;{digest}"
    selected = select_curated_sites(candidate, policy, jar)
    result = BuildResult(
        config=merge_curated_sites(result.config, selected),
        mirrors=result.mirrors + (MirrorRequest(source_url, repository_path, digest),),
    )
```

- [ ] **Step 5: Replace direct promotion with analysis-only CLI**

Add `promotion-report --source <id> --policy <path>`. The report includes candidate hash/site count, requested keys, selected count, prefixes, collisions, Spider/Jar facts, regional dependency warnings, and `eligible`. It performs no mirror, stable, playlist, health, Git, or remote writes.

Keep `promote` only as a compatibility error that exits 2 with: `direct promotion is disabled; review a policy and sources/promotions.json, then run compose`. Remove the old `promote_source` write path after its callers/tests are migrated.

- [ ] **Step 6: Re-run atomic composition and invariant tests**

Run:

```powershell
python -m unittest tests.test_curation tests.test_build tests.test_refresh -v
python scripts/refresh.py compose
python scripts/refresh.py verify --regions us cn
python -m unittest discover -s tests -v
```

Expected: both stable configs still contain 49 sites and exactly 35 `🐮` sites; the two LiveConfigs and automatic playlists remain valid; CN stable JSON contains no GitHub hostname.

- [ ] **Step 7: Commit**

```powershell
git add hometv/curation.py hometv/build.py hometv/refresh.py scripts/refresh.py sources/promotions.json tests/test_curation.py tests/test_build.py tests/test_refresh.py
git commit -m "Gate source promotion through reviewed manifests"
```

### Task 5: Live Endpoint Evidence, Documentation, and Draft-PR Update

**Files:**
- Modify: `README.md`
- Modify: `sources/discovered-endpoints.json` only with actual probe evidence.
- Modify: `sources/registry.json` only for alternates that pass the reviewed probe gate.
- Generate: `health/sources/nitan-dm.json`
- Generate: `health/sources/wangerxiao.json`
- Generate: `health/sources/aowu.json`
- Generate: `health/sources/fantaiying.json`
- Generate: `health/sources/ok.json`
- Modify when refreshed: `candidates/nitan-dm/{upstream.json,metadata.json}`
- Modify when refreshed: `candidates/wangerxiao/{upstream.json,metadata.json}`
- Generate when usable/degraded: `candidates/aowu/{upstream.json,metadata.json}`
- Generate when usable/degraded: `candidates/fantaiying/{upstream.json,metadata.json}`
- Generate when usable/degraded: `candidates/ok/{upstream.json,metadata.json}`
- Modify when dependency mirrors refresh: `vendor/manifest.json`, `vendor/nitan/**`, and `vendor/wanger/**`
- Create: `docs/verification/2026-08-16-five-source-health.md`

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces current US-origin source-health evidence without changing stable delivery.

- [ ] **Step 1: Document owner operations before live probing**

README must list the five sources, explain `usable|degraded|unavailable`, show `candidates --probe-origin`, `probe-endpoint`, and `promotion-report`, state that discovered URLs are not runtime endpoints, and repeat that recovery never changes stable automatically.

- [ ] **Step 2: Snapshot release and candidate state**

Record HEAD, index tree, status, SHA-256 and byte counts for `stable/us.json`, `stable/cn.json`, both LiveConfigs, and both automatic playlists. Record current candidates and source-health presence. Abort if the tracked worktree is dirty.

- [ ] **Step 3: Probe every discovered address read-only**

Run exactly:

```powershell
python scripts/refresh.py probe-endpoint --source aowu --url "http://itv666.cc/aowu/config.webp"
python scripts/refresh.py probe-endpoint --source fantaiying --url "http://www.饭太硬.net/tv"
python scripts/refresh.py probe-endpoint --source fantaiying --url "http://www.饭太硬.top/tv/"
```

Save the JSON outputs in the verification document. Update each catalog record's `last_checked_at` and sanitized evidence. If and only if a probe returns `usable|degraded`, has non-empty sites, and contains no policy error, copy that exact URL into the source's registry endpoints with role `alternate`, the catalog provenance, and the probe timestamp as `reviewed_at`; set the catalog status to `promoted`. Otherwise set it to `unavailable` and do not change the runtime registry.

- [ ] **Step 4: Refresh all five candidates from reviewed endpoints**

Run:

```powershell
python scripts/refresh.py candidates --probe-origin local-us-network
```

Expected: five health files are written. Nitan and Wang are blocking if unavailable; Aowu/Fantaiying/OK may honestly remain unavailable without failing the command. Any valid recovered backup writes an isolated candidate only.

- [ ] **Step 5: Prove release artifacts did not change**

Recompute the Step 2 hashes and require equality. Parse both stable JSON files and assert 49 sites and 35 `🐮` sites. Run static regional verification and search CN documents for GitHub hosts:

```powershell
python scripts/refresh.py verify --regions us cn
rg -n "github\.com|raw\.githubusercontent\.com" stable/cn.json stable/live-cn.json
```

Expected: static verification has no errors and the search returns no matches.

- [ ] **Step 6: Record honest verification evidence**

Record commit/base, UTC time, Python version, probe origin, every attempted endpoint, status/error, selected endpoint, source/candidate hashes, site counts, warnings, stable hashes, and limitations. State explicitly that a US probe neither proves mainland reachability nor validates every media URL. Do not include raw query values or credentials.

- [ ] **Step 7: Run full repository verification**

Run:

```powershell
python -m unittest discover -s tests -v
python -m py_compile hometv/registry.py hometv/fetch.py hometv/source_candidates.py hometv/refresh.py scripts/refresh.py
git diff --check
git status --short
```

Expected: tests pass and every changed path is within this task's declared evidence/candidate/health/documentation scope.

- [ ] **Step 8: Commit evidence and candidate state**

Stage explicit paths only. Do not stage `stable/**` or `vendor/live/auto-*.m3u`:

```powershell
git add -- README.md sources/registry.json sources/discovered-endpoints.json candidates health/sources vendor/manifest.json vendor/nitan vendor/wanger docs/verification/2026-08-16-five-source-health.md
git restore --staged stable vendor/live/auto-us.m3u vendor/live/auto-cn.m3u 2>$null
git commit -m "Record five-source candidate health"
```

The existing `candidates` directory is always present; absent backup-source
subdirectories are not an error and must not be fabricated. Before committing,
inspect `git diff --cached --name-only` and reject any staged path outside the
explicit candidate, health, manifest, reviewed mirror, registry, README, and
verification-document scope above.

- [ ] **Step 9: Push the source-only branch and update the existing draft PR**

Re-run the full suite, push the reviewed source-only HEAD to `origin/agent/curated-wanger-implementation`, update draft PR #2 to describe five-source quarantine, and wait for all checks. Do not mark ready, merge, synchronize Gitee, or change N1.

---

## Final Verification

Before claiming the plan complete:

```powershell
python -m unittest discover -s tests -v
python scripts/refresh.py verify --regions us cn
python -m json.tool sources/registry.json > $null
python -m json.tool sources/discovered-endpoints.json > $null
python -m json.tool sources/promotions.json > $null
git diff --check
```

Confirm:

- exact five-source registry and five source-health files;
- Nitan/Wang valid candidates;
- honest candidate-or-unavailable state for Aowu/Fantaiying/OK;
- stable US/CN remain 49 sites with 35 Wang sites;
- candidate refresh cannot mutate stable or automatic playlists;
- direct promotion is disabled;
- draft PR checks pass;
- Docker, Gitee, merge, and N1 remain untouched.
