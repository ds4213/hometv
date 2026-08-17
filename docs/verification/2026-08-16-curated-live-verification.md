# Curated VOD and Live verification record — 2026-08-16

## Snapshot

- Branch under preparation: `agent/curated-wanger-implementation`.
- Task-6 base: `e593b365dd3ed8d6eaff83d4a92f5951b523c4f7` (`Harden composed playlist refresh`).
- Initial verification-record commit: `9e80c7c723001539a42c41ef4b8335bfaa632e4a` (`Document curated HomeTV delivery`).
- Recorded at: `2026-08-17T00:02:53.9542158Z` (UTC).
- Runtime: Python `3.11.9`.
- Unit suite: `79` tests passed (`python -m unittest discover -s tests -v`).
- Probe origin: `local-static-validation`; no network probe was performed for this record.

This is a **pre-generation** record. Task 7 has not yet composed and checked in the new curated stable and automatic-live artifacts, so it would be incorrect to represent the current checkout as a completed delivery release.

## Checked-in artifact state

| Artifact | Current result |
| --- | --- |
| `stable/us.json` | Valid legacy JSON; 14 sites; 0 `🐮` curated Wang sites. |
| `stable/cn.json` | Valid legacy JSON; 14 sites; 0 `🐮` curated Wang sites. |
| `stable/live-us.json` | Missing; will be produced by `compose`. |
| `stable/live-cn.json` | Missing; will be produced by `compose`. |
| `vendor/live/auto-us.m3u` | Missing; will be seeded and guarded by `compose`. |
| `vendor/live/auto-cn.m3u` | Missing; will be seeded and guarded by `compose`. |

Accordingly, `python scripts/refresh.py verify --regions us cn` exits with an error because `stable/live-us.json` is absent. JSON parsing succeeds for the two existing VOD files. The planned JSON checks for both LiveConfig files and the planned mainland GitHub-dependency search cannot be completed until Task 7 creates those files. The exact planned generated VOD counts are the current Nitan count plus 35 curated Wang sites; they are not claimed as present here.

## Expected LiveConfig shape after composition

The implemented builder and its unit tests require this exact source order for both regions:

1. `HomeTV 自动（中国）`
2. `HomeTV 备用（Kimentanm）`
3. `HomeTV 临时赛事`

Each has `ua: okhttp/4.12.0` and `timeout: 15`; only the first has `boot: true`. The automatic-playlist channel counts are **not available** because neither `auto-us.m3u` nor `auto-cn.m3u` exists before composition. Task 7 must record their actual guarded channel counts and SHA-256 values after generation.

## Candidate and Spider evidence available in this checkout

| Item | Source / expected hash | Mirrored evidence available now |
| --- | --- | --- |
| Nitan candidate | `https://nitan.ggff.net/config-dm.json`; candidate SHA-256 `1877aa02c8f073e0df754a12eae2893b047a3e8861d10cb08e821595cd7e8901` | Nitan Spider source is `https://github.com/nitan-tv/nitan/raw/refs/heads/main/awdm.png`; `vendor/nitan/awdm.png` SHA-256 `c6dade7d08405128d8708df27d8cc4796907f35dd4c33626a220f0d8f8e45fc5`. The source does not declare an MD5. |
| Wang candidate | `https://9280.kstore.vip/aiwex.json`; candidate SHA-256 `b05dbe5d2902bef7f2c2b008bb9135b1f0eae3ef3a31bca8e9f54f3aa20bd43c` | Spider source `http://oss4liview.moji.com/thd_file/2026/08/14/f9c4d189ee5f4ca87021c3b2893133a9.jpg`; declared MD5 `dd932e5eb6170df1019c1ef3c9fe0b4b`. `vendor/wanger/spider.jpg` does not yet exist, so no mirrored Wang SHA-256 or actual MD5 is available before composition. |
| Kimentanm seed | `https://raw.githubusercontent.com/Kimentanm/aptv/refs/heads/master/m3u/iptv.m3u` | `vendor/live/kimentanm.m3u` SHA-256 `c35c1109c98deda9122429e2e78bf9fd0bdd8ca0dc5dd1acd75c332a8b761422`; this is a seed, not either published automatic playlist. |

The Nitan candidate metadata records SHA-256 `dc3d60a80fde8d3669c602a15d386058e240e0aabf1739d381fbb1f622c6ab8e`; the Wang candidate metadata records SHA-256 `20fd39d7c3e1406ac43029fa2c42d0708fbb2b6de4ee722251c9c5714654f354`. The table uses the byte-level hashes measured in this checkout.

## Delivery limitations and required next evidence

- This record contains no mainland carrier test and makes no claim that a China Telecom, China Unicom, or China Mobile node can play media.
- US static checks do not prove mainland media playback.
- Gitee reachability, once checked, does not prove that every third-party stream, Spider, or upstream video API will remain playable.
- After a reviewed GitHub release is synchronized to Gitee, Task 7 must run the planned delivery checks from all three mainland carriers, retain their timestamps and SHA-256 values, and update this record with the generated artifact counts and hashes.
