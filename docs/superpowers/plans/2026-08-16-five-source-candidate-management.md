# Five-Source Candidate Management Implementation Plan

> **For implementation:** Use `superpowers:test-driven-development` and make
> only the changes listed here.

**Goal:** Check five configured sources, save usable candidates, record simple
health, and leave stable delivery unchanged.

**Keep it simple:** Retain registry schema 1 and one URL per source. Do not add
endpoint fallback, discovery catalogs, promotion manifests, generic adapters,
Docker, Gitee, or N1 work.

### Task 1: Enable the Exact Five Sources

**Files:**
- Modify: `sources/registry.json`
- Modify: `tests/test_registry.py`

- [ ] Add a failing production-registry test requiring the ordered IDs
  `nitan-dm`, `wangerxiao`, `aowu`, `fantaiying`, `ok`, with all enabled and
  both regions configured.
- [ ] Require Nitan and Wang to have `stable_regions` `("us", "cn")`; require
  the other three to have none.
- [ ] Run `python -m unittest tests.test_registry -v` and observe the expected
  failure from the three disabled sources and Wang's old stable-region value.
- [ ] Update only `sources/registry.json`; remove obsolete disabled reasons.
- [ ] Re-run the registry tests and commit:

```powershell
git add sources/registry.json tests/test_registry.py
git commit -m "Enable all five candidate sources"
```

### Task 2: Write Simple Per-Source Health

**Files:**
- Modify: `hometv/refresh.py`
- Modify: `scripts/refresh.py`
- Modify: `.github/workflows/refresh-candidates.yml`
- Modify: `tests/test_refresh.py`

- [ ] Add failing tests proving:
  - every attempt writes `health/sources/<id>.json`;
  - success writes `status: "updated"`, candidate path and SHA-256;
  - failure writes `status: "failed"` and a short message;
  - failure preserves existing candidate and metadata bytes;
  - candidate-only failure is nonblocking;
  - Nitan/Wang failure is blocking;
  - no candidate refresh changes stable or automatic playlists.
- [ ] Run `python -m unittest tests.test_refresh -v` and observe failures for
  missing health and blocking fields.
- [ ] Implement `_write_source_health(root, source, result)` in
  `hometv/refresh.py` using JSON plus a same-directory temporary replacement.
- [ ] In `refresh_candidates`, validate `sites` as a non-empty list, retain
  Wang's curation gate, do not touch dependency mirrors, write a candidate only
  after validation, then write health for both success and failure.
- [ ] Add `blocking` to every result. It is true only when a failed source has
  non-empty `stable_regions` or persistence itself fails.
- [ ] Change the `candidates` CLI exit code to test `blocking`, not every backup
  source failure.
- [ ] Keep candidate-generated writes limited to `candidates` and `health`;
  keep the existing stable/live exclusions.
- [ ] Run focused and full tests, then commit:

```powershell
python -m unittest tests.test_refresh -v
python -m unittest discover -s tests -v
git add hometv/refresh.py scripts/refresh.py .github/workflows/refresh-candidates.yml tests/test_refresh.py
git commit -m "Record five-source refresh health"
```

### Task 3: Probe Current URLs and Save Honest State

**Files:**
- Modify if a tested alternate is better: `sources/registry.json`
- Generate/modify: `candidates/<source-id>/upstream.json`
- Generate/modify: `candidates/<source-id>/metadata.json`
- Generate: `health/sources/<source-id>.json`
- Modify: `README.md`
- Create: `docs/verification/2026-08-16-five-source-health.md`

- [ ] Hash and record the six current release outputs before network work:
  `stable/us.json`, `stable/cn.json`, both LiveConfigs, and both automatic
  playlists.
- [ ] Probe the five registry URLs from the current US network. Also test only
  these known alternates manually:

```text
http://itv666.cc/aowu/config.webp
http://www.饭太硬.net/tv
http://www.饭太硬.top/tv/
```

- [ ] If an alternate returns a valid non-empty FongMi config while its primary
  does not, replace that source's single registry URL. Otherwise keep the
  primary. Record all results as US-origin evidence, not mainland proof.
- [ ] Run `python scripts/refresh.py candidates`. Five health files must exist.
  Successful sources have candidates; failed sources retain their previous
  candidates or have none.
- [ ] Update README with the one command to refresh, the health-file location,
  and the rule that backup sources are not automatically added to stable.
- [ ] Recompute all six release hashes and require exact equality. Run:

```powershell
python scripts/refresh.py verify --regions us cn
python -m unittest discover -s tests -v
python -m py_compile hometv/refresh.py scripts/refresh.py
git diff --check
```

- [ ] Stage only source registry, candidates, source health, README, and
  evidence. Explicitly exclude vendor, stable, and automatic playlists. Commit
  the honest current state.

### Final Boundary

Do not push, merge, synchronize Gitee, modify N1, or start Docker during these
three tasks. Present the verified local result for owner review first.
