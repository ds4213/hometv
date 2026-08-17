# Curated VOD and Live verification record — 2026-08-16

## Generated snapshot

- Branch under preparation: `agent/curated-wanger-implementation`.
- Generation base: `71eadcf6b2b28a261884adbb66d0b1af7809fd77` (`Harden composed playlist refresh`).
- Generated and verified on: `2026-08-17T00:13:05.678249+00:00` (UTC; the later of the two network health reports).
- Runtime: Python `3.11.9`.
- Unit suite: `79` tests passed before generation and again after evidence collection (`python -m unittest discover -s tests -v`).
- Static verification: `python scripts/refresh.py verify --regions us cn` completed with warnings only: the intentional cleartext event dependency.
- Network probe origin: `local-us-network`. This is a US-origin approximation, **not** mainland delivery proof.

## Final generated artifacts

| Artifact | Final count / SHA-256 |
| --- | --- |
| `stable/us.json` | 49 sites: 14 Nitan plus exactly 35 curated `🐮` Wang sites; `a013ddb348b33411d2303de5b2aae6df63b0053d2ae23570ad7b3f179e502a70` |
| `stable/cn.json` | 49 sites: 14 Nitan plus exactly 35 curated `🐮` Wang sites; `5a9fa893ef63a0c73ca695bef81605ce625c86b2a5fdf8ce4b2a3a0de1917d77` |
| `stable/live-us.json` | three ordered sources; `b14d20c5c198611c5750d01f7395dc854f42aa490e79eae44e4f05a848f153af` |
| `stable/live-cn.json` | three ordered sources; `992ca06981143a0e8e4fe521f09e120c25e6b3b99983182ed4f4a9763f90c012` |
| `vendor/live/auto-us.m3u` | 123 guarded channels; `d11bca876d93fd2501503a4f8e0110fe34182ca32d41946a6376c42b9df32f75` |
| `vendor/live/auto-cn.m3u` | 123 guarded channels; `d11bca876d93fd2501503a4f8e0110fe34182ca32d41946a6376c42b9df32f75` |
| `vendor/wanger/spider.jpg` | 983,208 bytes; SHA-256 `5acc35791d3cd08b0bcb3f04219db847aca1d75b2eda9e526b6af805d3691402` |

Both automatic playlists parse successfully and pass the regional guards; the CN playlist includes CCTV and `卫视`. The CN VOD and LiveConfig JSON have no GitHub hostname. All 35 Wang `jar` references in each regional VOD config use the same expected MD5, `dd932e5eb6170df1019c1ef3c9fe0b4b`, which matches the final mirrored Spider bytes.

The LiveConfig source order is identical in both regions:

1. `HomeTV 自动（中国）` — the only `boot: true` source.
2. `HomeTV 备用（Kimentanm）`.
3. `HomeTV 临时赛事`.

Every entry uses `ua: okhttp/4.12.0` and `timeout: 15`. The expected cleartext warning is retained for the temporary event source; no validation errors were found.

## Candidate and mirror evidence

| Item | Final evidence |
| --- | --- |
| Nitan candidate | `https://nitan.ggff.net/config-dm.json`; SHA-256 `dc3d60a80fde8d3669c602a15d386058e240e0aabf1739d381fbb1f622c6ab8e` |
| Wang candidate | `https://9280.kstore.vip/aiwex.json`; SHA-256 `20fd39d7c3e1406ac43029fa2c42d0708fbb2b6de4ee722251c9c5714654f354` |
| Wang Spider | Mirrored from `http://oss4liview.moji.com/thd_file/2026/08/14/f9c4d189ee5f4ca87021c3b2893133a9.jpg`; expected and actual MD5 both `dd932e5eb6170df1019c1ef3c9fe0b4b` |
| Kimentanm seed | `vendor/live/kimentanm.m3u` was refreshed as a hash-checked mirror during `candidates`, then used as the seed for both automatic playlists. Source: `https://raw.githubusercontent.com/Kimentanm/aptv/refs/heads/master/m3u/iptv.m3u`; final 21,944-byte manifest entry and SHA-256 `6bca02295ddf751419889a72f87dfd0fe6f981e3b447a6bcb7e6f476446e93da`. |

## Network-probe evidence and limitations

Network verification ran after the static check with `--probe-origin local-us-network`. It found 18 of 29 US probes and 13 of 18 CN probes usable. The health records preserve every raw probe outcome.

- The repository-owned US Spider and automatic playlist URLs returned 404 because this generated commit has deliberately **not** been pushed or released yet.
- The US-only wallpaper host could not be encoded by the local HTTP client; several US DoH URLs rejected generic HTTP requests or had local TLS/DNS errors.
- Both Kimentanm EPG URLs returned 403, and the event EPG exceeded the 4 MiB probe cap.
- CN DoH probe endpoints returned 400/502 from this US-origin environment.
- The event playlist itself and its sampled media target were reachable during this run.

These are recorded network limitations, not static schema or generation invariant failures. They do not prove availability from China. After a reviewed GitHub release is synchronized to Gitee, delivery must still be checked from China Telecom, China Unicom, and China Mobile nodes, recording carrier, city, time, HTTP status, byte count, elapsed time, and SHA-256. Those checks are delivery evidence only; they do not prove every third-party media stream remains playable.

## Commands used

```text
python -m unittest discover -s tests -v
python scripts/refresh.py candidates
python scripts/refresh.py compose
python scripts/refresh.py verify --regions us cn
python scripts/refresh.py verify --regions us cn --network --probe-origin local-us-network
```

Final local checks also parsed all four JSON documents, parsed and region-validated both automatic M3U files, recomputed the final hashes above, confirmed the 35-site and LiveConfig-order invariants, and checked the working diff for whitespace errors and allowed paths only.
