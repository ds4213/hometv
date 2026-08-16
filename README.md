# HomeTV

Managed FongMi configuration delivery for an N1 box. GitHub is the source of truth. The verified `main` branch is mirrored to Gitee for mainland delivery.

## Permanent configuration paths

US configuration:

```text
https://raw.githubusercontent.com/ds4213/hometv/main/stable/us.json
```

Mainland configuration:

```text
https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json
```

The mainland JSON contains Gitee Raw dependency paths and passed mainland China Telecom, China Unicom, and China Mobile checks on 2026-08-16. See `docs/verification/2026-08-16-gitee-verification.md`.

## Add another interface

Add one object to `sources/registry.json`:

```json
{
  "id": "short-stable-id",
  "name": "Display name",
  "url": "https://example.com/config.json",
  "regions": ["us", "cn"],
  "enabled": true,
  "stable_regions": []
}
```

Then run:

```powershell
python scripts/refresh.py candidates
python -m unittest discover -s tests -v
```

The refresh writes only to `candidates/`, `vendor/`, and health metadata. It never replaces `stable/`.

## Promote a verified candidate

```powershell
python scripts/refresh.py promote --source nitan-dm --regions us cn
python scripts/refresh.py verify --regions us cn
```

Different upstream configurations stay isolated because they may require incompatible Spider bundles. Promotion replaces the complete regional configuration rather than merging unrelated sites.

## Roll back

Find the last known-good commit and revert the promotion commit through Git history. Do not delete the stable paths; FongMi should keep using the same URL.

## Health-report boundary

GitHub Actions runs from an overseas cloud network. Its reports use `probe_origin: github-actions-us-approximation` and do not claim mainland reachability. Mainland multi-carrier checks and the final Gitee Raw end-to-end check are recorded separately under `docs/verification/`.

## Safety

- Never commit passwords, cookies, access tokens, cloud-drive credentials, or signed personal URLs.
- Treat Spider JAR, JavaScript, and Python changes as executable-code updates.
- Scheduled automation refreshes candidates only. Stable promotion is explicit.
- Push only verified `main` commits to Gitee; do not promote candidate configurations automatically.
