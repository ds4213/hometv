# Five-Source Candidate Management Design

## Status

Approved in conversation on 2026-08-16. This specification covers source
management only. Docker/NAS automation, Gitee synchronization, and N1 changes
are explicitly deferred.

## Goal

Manage exactly five FongMi source families in one repository without allowing
an unavailable or newly recovered upstream to disrupt the parents' stable N1
configuration:

1. 泥潭弹幕版 (`nitan-dm`)
2. 王二小主力三代 (`wangerxiao`)
3. 嗷呜 (`aowu`)
4. 饭太硬 (`fantaiying`)
5. OK (`ok`)

The existing stable US and China Vod configurations remain at 49 sites (14
Nitan plus 35 curated Wang sites) until a separately reviewed promotion is
approved. Candidate refresh never changes stable Vod, LiveConfig, or automatic
playlists.

## User-Facing Outcome

The N1 continues to use the same permanent URLs and requires no new setting:

- China Vod: `https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json`
- China Live: `https://gitee.com/ds4213tv/hometv/raw/main/stable/live-cn.json`
- US Vod: `https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json`
- US Live: `https://raw.githubusercontent.com/ds4213/hometv/main/stable/live-us.json`

Unavailable backup sources are not shown on the N1. They remain visible to the
owner through repository health reports and can be reviewed remotely if they
recover.

## Architecture

```text
reviewed endpoint registry
        |
        v
candidate fetch and validation
        |-- failure --> health report only; preserve last good candidate
        |
        `-- success --> isolated candidate snapshot + reproducible metadata
                              |
                              v
                         owner review
                              |
                              v
                   per-source curated allowlist
                              |
                              v
               atomic regional composition and PR review
```

The stable delivery path and candidate-management path are separate. A
scheduled candidate run may update candidate snapshots, health reports, and
hash-checked dependency mirrors. It cannot invoke stable composition or write
any path under `stable/` or `vendor/live/auto-*.m3u`.

## Endpoint Registry

`sources/registry.json` remains the source of truth and advances to an explicit
endpoint-list schema. Each source contains:

- immutable `id` and display `name`;
- supported `regions` and current `stable_regions`;
- an ordered `endpoints` array;
- `candidate_mode: "quarantine"`;
- `promotion: "manual"`;
- a display prefix reserved for promoted sites;
- a disabled reason when no endpoint is currently usable.

Each endpoint record contains:

- `url`;
- `role` (`primary` or `alternate`);
- human-readable `provenance`;
- `reviewed_at`;
- optional notes, never credentials.

The initial ordered endpoint inventory is:

| Source | Primary | Alternate candidates |
|---|---|---|
| Nitan | `https://nitan.ggff.net/config-dm.json` | none initially |
| Wang | `https://9280.kstore.vip/aiwex.json` | none initially |
| Aowu | `https://cnb.cool/aooooowuuuuu/FreeSpider/-/git/raw/main/config` | `http://itv666.cc/aowu/config.webp` (discovered, must be verified before registry activation) |
| Fantaiying | `http://www.饭太硬.com/tv` | `http://www.饭太硬.net/tv` and `http://www.饭太硬.top/tv/` (discovered, must be verified before registry activation) |
| OK | `http://ok213.top/tv` | none initially |

Discovery does not equal trust. An alternate is attempted only after its exact
URL and provenance have been reviewed into the registry. Runtime redirects do
not silently become new registry entries.

## Candidate Fetching

For each source, the fetcher tries reviewed endpoints in their stored order.
One successful, fully validated endpoint ends the attempt sequence. Every
attempt is recorded in the source health report with a sanitized URL, result,
HTTP status when available, elapsed time, and a query-free error summary.

Fetch constraints:

- public HTTP or HTTPS only;
- no URL userinfo;
- no private, loopback, link-local, metadata-service, or ambiguous host;
- no sensitive query keys;
- every redirect target must pass the same URL policy;
- bounded connection/read timeout, redirect count, and response size;
- UTF-8 JSON object response, not HTML, an archive, or a login/error page;
- non-empty `sites` array;
- unique non-empty site keys;
- structurally valid `api`, `ext`, `jar`, and Spider references.

A source-specific validator may add stronger rules. Wang continues to require
the existing exact 35-key curated policy before it can affect stable output.

## Candidate and Health Storage

Successful candidates use the existing layout:

```text
candidates/<source-id>/upstream.json
candidates/<source-id>/metadata.json
```

Metadata records both the original response facts and the canonical saved-file
facts: selected endpoint, fetch time, response bytes/SHA-256, candidate
bytes/SHA-256, site count, and applicable Spider reference.

Current detection state is stored separately:

```text
health/sources/<source-id>.json
```

Health status is one of:

- `usable`: configuration and required dependencies pass validation;
- `degraded`: configuration is structurally usable but has reachability,
  regional-delivery, or dependency warnings;
- `unavailable`: DNS, timeout, HTTP, content, JSON, or structural validation
  failed for every reviewed endpoint.

On failure, only the health report changes. The last known-good candidate and
its metadata remain byte-for-byte unchanged. If a source has never succeeded,
its candidate files remain absent.

## Manual Promotion

A recovered source is never merged automatically. Promotion requires:

1. a candidate diff showing site count, keys, names, API types, Spider/Jar,
   parses, and dependency URLs;
2. collision analysis against the current stable base and every other promoted
   source;
3. a committed per-source allowlist of approved site keys;
4. source-prefix naming for new sites:
   - Wang `🐮`
   - Aowu `🐺`
   - Fantaiying `🍚`
   - OK `🆗`;
5. source-specific Spider/Jar isolation and hash-checked mirroring;
6. independent US and China builds;
7. full static validation, network evidence, tests, and owner review;
8. atomic stable composition followed by GitHub pull-request review.

Existing stable keys win. A collision is an error; the system does not silently
overwrite a site or invent a renamed key. A source requiring incompatible
global fields receives a source-specific adapter or remains quarantined.

For repository-owned dependencies, US output uses GitHub Raw and China output
uses Gitee paths. China output may not contain GitHub repository hosts. A US
network probe is recorded as a US approximation and never presented as proof
of mainland availability. China delivery evidence is required before a newly
promoted source is synchronized to Gitee.

Promotion reuses the existing all-or-nothing composition transaction. Both Vod
documents, both LiveConfig documents, and both automatic playlists are staged
and revalidated before any destination is replaced, even when the playlist
bytes are unchanged.

## Scheduled and Manual Operations

The existing candidate workflow may check all five sources on its daily or
manual run. Its commit allowlist is limited to candidates, source health,
manifest data, and reviewed dependency mirrors. Stable JSON and automatic
playlists are explicitly excluded.

Recovery produces a candidate and a review report only. The owner must approve
the allowlist and promotion in a later change. Gitee synchronization and N1
configuration remain separate explicit actions.

## Error Handling and Security

- Errors and stored health data redact query values, userinfo, tokens, cookies,
  and authorization data.
- Candidate and health files are written atomically in their destination
  directories.
- A failed endpoint does not prevent later reviewed endpoints for the same
  source from being attempted.
- A failed source does not block health updates for the other four sources.
- Conflicting mirror requests, hash mismatches, unexpected content types, and
  invalid dependency URLs fail closed.
- The repository stores configuration metadata and reviewed mirrored runtime
  dependencies only; it does not store media files or credentials.

## Testing Strategy

Automated tests cover:

- exact five-source registry schema and endpoint order;
- rejection of unknown endpoint fields and unreviewed runtime alternates;
- primary failure followed by alternate success;
- every-endpoint failure with last-good candidate preservation;
- HTML, empty, oversized, invalid JSON, private host, userinfo, sensitive query,
  redirect, and duplicate-key rejection;
- health status and sanitized per-attempt evidence;
- candidate canonical hashes and atomic writes;
- scheduled refresh inability to change stable JSON or automatic playlists;
- stable key/name/API/Spider collision detection;
- per-source allowlist and prefix behavior;
- mirror hash mismatch and conflicting-path rejection;
- independent regional dependency rewriting and the China no-GitHub invariant;
- all-or-nothing stable promotion and rollback.

Live endpoint tests remain evidence, not absolute availability guarantees.

## Rollout and Completion Criteria

This source-management increment is complete when:

- all five named sources conform to the reviewed registry schema;
- each source has a current health report;
- Nitan and Wang retain valid candidates;
- Aowu, Fantaiying, and OK either have a valid isolated candidate or an honest
  `unavailable` report with all reviewed attempts;
- candidate refresh leaves the current 49-site stable US and China configs
  unchanged;
- all automated tests and the GitHub draft-PR checks pass.

No Gitee push, N1 change, Docker/NAS work, or automatic promotion is part of
this increment.

## Non-Goals

- Discovering an unlimited catalog of public TVBox/FongMi interfaces.
- Automatically merging every site from a recovered source.
- Proving that every third-party media URL plays from every Chinese carrier.
- Deploying Docker IPTV generation or persistent Gitee automation.
- Changing the parents' permanent FongMi configuration URLs.
