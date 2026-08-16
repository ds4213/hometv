# HomeTV configuration distribution design

## Goal

Provide two stable FongMi configuration URLs for the same N1 box family:

- `stable/us.json` for devices used outside mainland China.
- `stable/cn.json` for devices used in mainland China.

The device URL must remain unchanged when an upstream interface fails. A maintainer promotes a verified candidate to the stable path, after which FongMi receives it on its next configuration reload.

Gitee is not part of the initial implementation. GitHub is built and verified first. Gitee synchronization happens only after the owner gives a separate explicit instruction.

## Source policy

Each upstream configuration is treated as a complete candidate because FongMi configurations commonly depend on a single top-level Spider bundle. Sites from configurations with different Spider bundles are not merged blindly.

The initial candidate is the Nitan danmaku configuration referenced by the USCardForum post. Additional candidates may include Wangerxiao and other interfaces after current URLs and dependencies are verified. Dead, redirected, HTML-only, or unresolvable endpoints remain disabled and are not published as stable sources.

No credentials, cookies, cloud-drive tokens, personal server keys, or authenticated URLs may be committed. Only content that the owner is authorized to use or redistribute may be mirrored.

## Repository layout

```text
stable/
  us.json
  cn.json
candidates/
  nitan-dm/
  wangerxiao/
  fantaiying/
  ok/
sources/
  registry.json
vendor/
  nitan/
  live/
health/
  us.json
  cn.json
scripts/
  fetch_sources.py
  validate_configs.py
.github/workflows/
  refresh-candidates.yml
```

`sources/registry.json` is the only normal entry point for adding an interface. Each record contains a stable identifier, display name, upstream URL, intended region (`us`, `cn`, or `both`), enabled state, and update policy.

## Adding a future interface

The owner provides a URL or adds one registry entry. Automation then:

1. Downloads the upstream response without publishing it.
2. Rejects login pages, CAPTCHA pages, empty bodies, invalid JSON, and unexpected content types.
3. Extracts the Spider, site APIs, extensions, live lists, parsers, and other remote dependencies.
4. Stores the full configuration in an isolated candidate directory.
5. Mirrors permitted static dependencies for the mainland candidate and rewrites only those URLs.
6. Runs regional reachability and format checks.
7. Produces a health report without placing secrets in logs.
8. Leaves the candidate unpublished until a maintainer promotes it.

Promotion replaces the contents behind `stable/us.json` or `stable/cn.json`; the FongMi URL on the box does not change. Rollback restores the previous known-good commit.

## Regional variants

The US variant preserves working upstream URLs where direct overseas access is reliable.

The mainland variant mirrors permitted static GitHub assets and live-list snapshots to the future Gitee repository. It replaces unsuitable overseas DNS-over-HTTPS entries with verified mainland alternatives. Dynamic VOD APIs are not mirrored as static files; they must pass mainland probes and remain external dependencies.

The mainland stable URL will eventually be:

```text
https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json
```

The GitHub stable URLs are:

```text
https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json
https://raw.githubusercontent.com/ds4213/hometv/main/stable/cn.json
```

## Validation

Validation has four layers:

1. Static validation: JSON parses, required structures have the expected types, duplicate keys and malformed URLs are reported.
2. Dependency validation: Spider and extension assets return successful responses and meet minimum size/content checks.
3. API validation: representative category, search, detail, and play requests are exercised where the interface protocol permits.
4. Regional validation: entry URLs, dependencies, APIs, playlists, and initial media segments are probed from mainland and overseas networks. A mainland cloud probe is an approximation; the final check is the parents' residential connection after the box returns to China.

An HTTP 200 response alone is insufficient. HTML error pages and playlists whose first media segments cannot be fetched are failures.

## Update and failure behavior

Scheduled refreshes update candidates only. Stable files never change automatically solely because an upstream changed. A failed fetch retains the last candidate and records the error. Multiple consecutive failures do not delete the working stable configuration.

Static dependencies are versioned with checksums. Unexpected Spider changes are flagged for review rather than promoted automatically. Health reports distinguish entry availability, dependency availability, API health, and actual media playback.

## Initial source findings

- Nitan's readable danmaku JSON endpoint currently responds, but it references GitHub-hosted static dependencies and overseas services.
- The forum's CNB Aowu URL currently returns 404.
- The old Wangerxiao address is now a landing page; its published current JSON endpoint is a separate URL and must be treated as a new candidate.
- The supplied Fantaiying and OK addresses are currently unusable from the overseas test location and require current verified replacements before inclusion.

## Acceptance criteria

- The two stable GitHub URLs return valid FongMi JSON.
- The US and mainland variants are generated from traceable candidates.
- Mainland static dependencies contain no remaining GitHub raw URLs unless explicitly documented as unavoidable.
- A new source can be added through one registry record without merging incompatible Spider bundles.
- Failed refreshes do not replace the last known-good stable configuration.
- Gitee remains untouched until the owner explicitly authorizes synchronization.
