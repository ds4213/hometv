# Five-Source Candidate Management Design

## Status

Approved in conversation on 2026-08-16. This replaces the earlier complex
endpoint-registry and generic-promotion proposal.

## Goal

Keep exactly five FongMi source families configured in the repository:

1. 泥潭弹幕版 (`nitan-dm`)
2. 王二小主力三代 (`wangerxiao`)
3. 嗷呜 (`aowu`)
4. 饭太硬 (`fantaiying`)
5. OK (`ok`)

Every refresh checks all five. A successful response is saved as an isolated
candidate. A failed response is recorded in a small health file and never
deletes or overwrites the last successful candidate.

## Deliberately Simple Structure

Keep the existing schema-1 registry and its single `url` per source. Do not add
an endpoint-list schema, discovery catalog, promotion manifest, generic source
adapter, or automatic fallback logic.

All five sources are enabled and support both `us` and `cn` candidate checks.
Only Nitan and Wang have `stable_regions: ["us", "cn"]`; Aowu, Fantaiying,
and OK remain candidate-only.

The initial URLs are:

| Source | URL |
|---|---|
| Nitan | `https://nitan.ggff.net/config-dm.json` |
| Wang | `https://9280.kstore.vip/aiwex.json` |
| Aowu | `https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config` |
| Fantaiying | `http://www.饭太硬.com/tv` |
| OK | `http://ok213.top/tv` |

If a known alternate is demonstrably better during the live check, replace the
single registry URL manually and record that fact in verification evidence.
There is no automatic fallback list.

## Refresh Behavior

The existing `candidates` command continues through all five sources:

- require a top-level JSON object with a non-empty `sites` list;
- keep Wang's existing exact 35-site curation check;
- do not refresh dependency mirrors; explicit `compose` owns that work;
- save other valid source responses without trying to merge them into stable;
- write `health/sources/<source-id>.json` after every attempt;
- on failure, update health only and preserve the previous candidate files.

Each health file contains only source ID/name/URL, UTC check time, status,
candidate path/hash when successful, or a short error when failed. No
credentials or response bodies are stored.

The CLI returns failure only when Nitan or Wang fails, because those two feed
the current stable configuration. Failure of a candidate-only source remains
visible but does not break the scheduled refresh.

## Stable Boundary

Candidate refresh cannot write `stable/**`, `vendor/**`, or
`vendor/live/auto-*.m3u`. The existing stable outputs remain 49 sites: 14
Nitan plus 35 curated Wang sites. Aowu, Fantaiying, and OK require a later
explicit owner decision before any curated sites are added.

## Testing and Completion

Tests prove the five-source registry, health output, last-known-good candidate
preservation, nonblocking candidate-only failures, blocking Nitan/Wang failure,
and the no-stable-write invariant.

The work is complete when all tests pass, five current health files exist, any
currently usable sources have candidate snapshots, and hashes of all six
stable/live outputs remain unchanged.

Docker/NAS work, Gitee synchronization, N1 changes, automatic promotion, and
complex endpoint discovery are out of scope.
