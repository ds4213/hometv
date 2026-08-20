# HomeTV

HomeTV provides managed FongMi configuration files for an N1 box. GitHub is the source of truth; reviewed `main` content is synchronized to Gitee for mainland delivery. Parents only need the appropriate permanent URL below.

## FongMi settings

```text
中国点播：https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json
中国直播：https://gitee.com/ds4213tv/hometv/raw/main/stable/live-cn.json
美国点播：https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json
美国直播：https://raw.githubusercontent.com/ds4213/hometv/main/stable/live-us.json
```

Set the point-on-demand URL in FongMi's `点播` setting and the matching live URL in its `直播` setting. These URLs are permanent: fixing or rolling back a bad release changes repository content, never the URL configured on the box.

## Owner operations

Run these commands from a reviewed checkout. They deliberately separate untrusted upstream input from the files parents consume.

### `candidates`

```powershell
python scripts/refresh.py candidates
```

Checks all five configured upstream interfaces and saves usable responses under
`candidates/`. Every attempt writes a small status file under
`health/sources/`. A failed source keeps its previous candidate; Aowu,
Fantaiying, and OK failures do not block Nitan and Wang from refreshing.

This command does not update dependency mirrors and cannot publish or replace
`vendor/**`, `stable/*.json`, or `vendor/live/auto-*.m3u`. A backup source is
never added to the parents' stable configuration automatically.

### `compose`

```powershell
python scripts/refresh.py compose
```

After reviewing candidates, builds the two curated VOD configurations, two LiveConfig documents, and the two guarded automatic playlists as one atomic release. Composition validates the 35 selected Wang sites, Spider hashes, regional repository URLs, and playlist guardrails before replacing any output. Review the resulting diff before committing it.

### `verify`

```powershell
python scripts/refresh.py verify --regions us cn
```

Performs static regional validation of both VOD and LiveConfig files. Add `--network --probe-origin <where-the-check-ran>` only when making a clearly labelled delivery check; an overseas check is not evidence of mainland media playback.

### `publish-live`

Use this only to validate and atomically replace one automatic playlist that was generated elsewhere:

```powershell
python scripts/refresh.py publish-live --profile cn --input ops/iptv-api/profiles/cn/output/ipv4/result.m3u
python scripts/refresh.py publish-live --profile us --input ops/iptv-api/profiles/us/output/ipv4/result.m3u
```

The command rejects malformed, unsafe, overly small, or sharply reduced playlists and retains the previous playlist on rejection.

## Rollback and safety

Roll back by reverting the bad content commit on GitHub `main`, then synchronize that reviewed result to Gitee. Do not delete or rename the four permanent paths above. Never commit passwords, cookies, access tokens, cloud-drive credentials, signed personal URLs, or personal server keys.

GitHub Actions refreshes candidates only. Its scheduled commit is restricted
to candidate data and health reports; it explicitly excludes `vendor/**`,
`stable/**`, and automatic playlists. Pull requests run tests and static
verification but never refresh, commit, or push release content.

## Verification boundary

See [the current verification record](docs/verification/2026-08-16-curated-live-verification.md) for artifact state and the limits of the available checks. Gitee reachability does not prove that every independent third-party stream will play, and a US check does not prove mainland media playback.
