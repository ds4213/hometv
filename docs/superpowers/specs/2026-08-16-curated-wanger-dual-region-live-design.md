# Curated Wang Er Xiao and dual-region live delivery design

Date: 2026-08-16

## Outcome

Provide two parent-friendly FongMi 5.6.1 configurations that retain the Nitan danmaku sources, add a curated subset of Wang Er Xiao sources with an independent Spider, and use dedicated live configuration URLs instead of pointing the Live setting at a Vod configuration.

The US home NAS will later run `Guovin/iptv-api` twice: one run produces a US-tested playlist, while the other produces a mainland-oriented playlist without deleting channels merely because they cannot play from a US IP.

## Scope boundaries

This work has two separately deployable phases:

1. **FongMi configuration phase:** curated Wang Er Xiao sites, mirrored Spider, dedicated US/CN live configs, and immediately usable fallback playlists.
2. **NAS automation phase:** two `iptv-api` profiles, guarded publication, GitHub-first delivery, and Gitee synchronization.

Phase 1 must work on the N1 before Phase 2 is allowed to replace either automatic playlist. The project does not attempt to provide paid memberships, private cookies, cloud-drive credentials, Emby accounts, WebDAV credentials, or a mainland proxy.

## Permanent URLs

| Region | Vod setting | Live setting |
| --- | --- | --- |
| Mainland China | `https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json` | `https://gitee.com/ds4213tv/hometv/raw/main/stable/live-cn.json` |
| United States | `https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json` | `https://raw.githubusercontent.com/ds4213/hometv/main/stable/live-us.json` |

The Vod files may continue to contain a `lives` fallback for fresh installations, but the N1 rollout explicitly configures the separate Live URL. This removes ambiguity between Vod loading and Live loading and makes empty-list failures independently diagnosable.

## Curated Wang Er Xiao integration

### Spider isolation

Nitan remains the global `spider`. The Wang Er Xiao Spider is downloaded, content-checked, hashed, and mirrored as a repository-owned artifact:

- GitHub path: `vendor/wanger/spider.jpg`
- Mainland delivery path: `https://gitee.com/ds4213tv/hometv/raw/main/vendor/wanger/spider.jpg`
- US delivery path: `https://raw.githubusercontent.com/ds4213/hometv/main/vendor/wanger/spider.jpg`

Every selected Wang Er Xiao `type=3` site receives its own `jar` field with the mirrored URL and upstream MD5 suffix. No Wang site is allowed to inherit Nitan's global Spider. Original site order and source-specific `ext`, headers, filters, and categories are preserved.

### Exact allowlist

The allowlist is stored as data, not embedded in transformation code. It contains the following source keys:

- 4K/general: `二小`, `玩偶`, `AiNewGuanYing`, `AiQwMkv`, `NewZhiZhen`, `AiNewLibvio`
- Direct/fast playback: `WexHanXiaoQuan`, `WexAiGuaZi`, `WexAiDuBoKu`, `WexAiYueYue`, `WexAiWenCai`, `WexAiV6DaShiXiong`, `WexAiV6TeGou`, `賤賤`, `WexAiYiYs`, `WexAiReBo`, `WexAiBoBo`, `WexAiIkanBot`
- Short drama: `DuanJuAiHaoKan`, `DuanJuAiQiMiao`, `DuanJuAiXingYa`
- Anime: `AnimeXiFan`, `AnimeCiYuanCheng`, `AnimeAiMiaoWu`
- Children/education/music: `ChildrenAiBaoBao`, `ChildrenAiBeiWa`, `少儿教育`, `小学课堂`, `MusicAiLiYuan`, `MusicAiIKtv`, `MusicAiKuWo`
- Sports: `SportAiFeiQiu`, `SportAiGuaZi`, `SportAiKanQiuTong`, `SportAiKanqiu`

The following classes remain excluded: configuration centers, personal cloud-drive entries, 115, Emby, AList, WebDAV, DIY Vod, push targets, search-only sources, duplicate Douban homes, and sources requiring user-owned credentials.

If an allowlisted key disappears upstream, candidate refresh reports it and keeps the last known-good stable configuration. A missing key must not silently shrink the stable file.

### Duplicate handling

Nitan sites are kept first. Wang sites are appended only when their `key` is unique. Display-name duplication is allowed only when keys and implementations differ; Wang names receive a consistent `🐮` prefix so parents can identify their origin. The final stable configuration must contain no duplicate site keys.

## Dedicated live configurations

`stable/live-cn.json` and `stable/live-us.json` are valid FongMi LiveConfig objects. Each has three sources in this order:

1. Region-specific automatic playlist (`vendor/live/auto-cn.m3u` or `vendor/live/auto-us.m3u`), selected by default.
2. Repository-mirrored Kimentanm playlist as a fallback.
3. Direct World Cup/event playlist as a temporary fallback while it remains non-empty and reachable.

Each Live entry specifies a unique name, URL, a suitable User-Agent, timeout, and EPG where available. Repository-owned mainland URLs use Gitee. Repository-owned US URLs use GitHub Raw. Cleartext direct event URLs remain warnings and are never the only live source.

Phase 1 seeds both automatic playlists from the known playlists after syntax validation, so the new Live URLs are useful before NAS automation is deployed.

## US NAS generation

`Guovin/iptv-api` is an external generator, not a source of channels. Its source subscriptions are limited to explicit entries tracked in this repository. Per the owner's 2026-08-16 decision, the NAS uses `guovern/iptv-api:latest`: each scheduled cycle pulls once, records the resolved image ID/digest, and runs both regional profiles with that same image. A pull or inspection failure aborts the cycle without replacing either known-good playlist.

Two isolated profiles run every 12 hours:

### US profile

- IPv4 preferred; IPv6 is excluded unless the US viewing network is confirmed to support it.
- Quick playback and speed testing are enabled from the US NAS.
- Dead, slow, HTML, and malformed streams are excluded.
- A small number of backup URLs per channel is retained.
- Output: `vendor/live/auto-us.m3u`.

### Mainland profile

- Inputs are fetched, normalized, de-duplicated, and syntax-checked from the US NAS.
- US media playback failure is not grounds for deletion because it can be caused by regional restrictions.
- IPv4 is preferred for broad compatibility at the parents' home.
- Output: `vendor/live/auto-cn.m3u`.

Mainland delivery checks verify the Gitee playlist and its repository-owned dependencies from China Telecom, China Unicom, and China Mobile. Those checks do not claim that every media URL is playable. Actual N1 playback feedback is the final signal for mainland-only streams.

## Publication guardrails

NAS output is staged before it can replace a known-good playlist. Publication is rejected when any of these is true:

- Output is not valid M3U or contains an HTML response.
- It contains fewer than 20 distinct channels.
- Channel count drops by more than 35% from the previous stable automatic playlist.
- It contains no CCTV or no provincial-satellite group for the mainland profile.
- It contains a URL with embedded credentials, access tokens, signed personal queries, or private LAN addresses.
- The same channel/URL pair is duplicated.

Rejected output is archived as diagnostic metadata without replacing the stable artifact. Accepted output is written atomically, health metadata is updated, and only the generated playlist and health files are committed. Candidate refresh may not modify the Wang allowlist or either stable Vod/Live JSON.

GitHub remains the source of truth. Automated Gitee delivery requires a repository-scoped credential and is enabled only after explicit authorization; no personal password is stored in the repository or NAS configuration.

## Verification

Automated tests cover:

- Exact Wang allowlist selection and preservation of upstream site fields.
- Per-site Wang Spider isolation for both regions.
- Duplicate-key rejection and missing-allowlist-key failure.
- US/Gitee URL rewriting with no GitHub dependency in mainland stable files.
- LiveConfig shape, source order, unique names, and independent US/CN paths.
- M3U validation, minimum channel count, drop-ratio guard, secret filtering, and atomic rejection.
- Candidate refresh never mutating stable files.

Release verification covers:

- All repository tests passing on Python 3.12 in GitHub Actions.
- HTTP/content/hash checks for both Spider artifacts and all four permanent config URLs.
- Mainland multi-carrier GET checks for `live-cn.json` and `auto-cn.m3u`.
- N1 running FongMi 5.6.1: Vod page shows Nitan plus prefixed Wang sources; Live page shows non-empty groups and channels; at least one channel from the automatic source and one fallback source plays.

## Rollout and rollback

1. Publish Phase 1 through a GitHub pull request and pass Actions.
2. Mirror the merged commit to Gitee and run mainland delivery checks.
3. Change the N1 Live setting to `stable/live-cn.json`, clear only FongMi's cache, and reload.
4. Verify parent-facing navigation and representative playback before enabling NAS publication.
5. Deploy the two NAS profiles and run once in dry-run mode.
6. Enable the 12-hour schedule only after the generated channel counts and samples are reviewed.

Rollback never changes the permanent URLs. Revert the bad commit or restore the previous generated M3U artifact; FongMi then receives the prior content at the same URL.
