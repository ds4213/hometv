# Five-Source Candidate Health Verification

## Scope

- Probe time: `2026-08-17T02:23:37Z`
- Probe origin: local US network; this is not mainland-China proof.
- Starting implementation HEAD: `717c8e617bbe8e455c68f706ae96ef35cc66a708`
- Python: `3.11.9`
- Candidate refresh does not compose, publish, or change stable/live outputs.

## Endpoint Results

| Source/address | Result | Evidence |
|---|---|---|
| Nitan primary | usable | HTTP 200; 4,686 response bytes; 14 sites; response SHA-256 `dc3d60a80fde8d3669c602a15d386058e240e0aabf1739d381fbb1f622c6ab8e` |
| Wang primary | usable | HTTP 200; 25,728 response bytes; 90 upstream sites; response SHA-256 `20fd39d7c3e1406ac43029fa2c42d0708fbb2b6de4ee722251c9c5714654f354`; stable remains limited to the reviewed 35 |
| Aowu primary | unavailable | HTTP 404 |
| Aowu alternate `itv666.cc` | rejected | HTTP 200 but `image/png` with PNG signature, not FongMi JSON |
| Fantaiying primary | unavailable | connection timed out after IDNA hostname conversion |
| Fantaiying `.net` alternate | rejected | HTTP 200 HTML page, not JSON |
| Fantaiying `.top` alternate | unavailable | request failed |
| OK primary | unavailable | DNS lookup failed |

No alternate replaced a registry URL because none returned a valid non-empty
FongMi JSON object.

## Saved Candidate State

| Source | Health | Candidate facts |
|---|---|---|
| `nitan-dm` | updated | 14 sites; 4,336 canonical bytes; SHA-256 `ed5f909cd3342ec2c4f6d6334b5e729f596ab2d235b731c43ab8c71f939a7113` |
| `wangerxiao` | updated | 90 upstream sites; 24,936 canonical bytes; SHA-256 `7dd87291c91cd4ec19f95cb42cd3765bd18fc109eabb055e1a8b553c2af3d0f0` |
| `aowu` | failed, nonblocking | no valid candidate written |
| `fantaiying` | failed, nonblocking | no valid candidate written |
| `ok` | failed, nonblocking | no valid candidate written |

Current per-source reports are stored under `health/sources/`.

## Release-Artifact Guard

The following SHA-256 hashes were recorded before the source probes and were
rechecked after refresh:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `stable/us.json` | 16,517 | `a013ddb348b33411d2303de5b2aae6df63b0053d2ae23570ad7b3f179e502a70` |
| `stable/cn.json` | 15,595 | `5a9fa893ef63a0c73ca695bef81605ce625c86b2a5fdf8ce4b2a3a0de1917d77` |
| `stable/live-us.json` | 752 | `b14d20c5c198611c5750d01f7395dc854f42aa490e79eae44e4f05a848f153af` |
| `stable/live-cn.json` | 732 | `992ca06981143a0e8e4fe521f09e120c25e6b3b99983182ed4f4a9763f90c012` |
| `vendor/live/auto-us.m3u` | 22,523 | `be9155a6769752f9f3b136763e6d51cd1cdfffa3016496c745943e004d945468` |
| `vendor/live/auto-cn.m3u` | 22,523 | `be9155a6769752f9f3b136763e6d51cd1cdfffa3016496c745943e004d945468` |

The hashes are identical before and after candidate refresh. No Docker, Gitee,
N1, stable configuration, or automatic playlist action was performed.
