from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

from hometv.build import BuildResult, build_cn, build_us, mirror_files
from hometv.fetch import FetchedConfig, FetchError, fetch_config, write_candidate
from hometv.registry import Source, load_registry
from hometv.validate import Finding, ProbeResult, probe_http, validate_config, write_health_report


GITEE_RAW_BASE = "https://gitee.com/ds4213tv/hometv/raw/main"


class RefreshError(RuntimeError):
    """Raised when a candidate cannot be promoted safely."""


def refresh_candidates(
    root: Path,
    fetcher: Callable[[Source], FetchedConfig] = fetch_config,
    mirror_func: Callable = mirror_files,
) -> list[dict]:
    results: list[dict] = []
    for source in load_registry(root / "sources" / "registry.json"):
        if not source.enabled:
            results.append(
                {
                    "source": source.id,
                    "status": "disabled",
                    "message": source.disabled_reason,
                }
            )
            continue
        try:
            fetched = fetcher(source)
            if "cn" in source.regions:
                cn_build = build_cn(fetched.content, GITEE_RAW_BASE)
                if cn_build.mirrors:
                    mirror_func(cn_build.mirrors, root)
            path = write_candidate(fetched, root / "candidates")
            results.append(
                {
                    "source": source.id,
                    "status": "updated",
                    "path": path.relative_to(root).as_posix(),
                    "sha256": fetched.sha256,
                }
            )
        except (FetchError, OSError, TypeError, ValueError, RuntimeError) as exc:
            results.append({"source": source.id, "status": "failed", "message": str(exc)})
    return results


def _source(root: Path, source_id: str) -> Source:
    for source in load_registry(root / "sources" / "registry.json"):
        if source.id == source_id:
            return source
    raise RefreshError(f"unknown source: {source_id}")


def _candidate(root: Path, source_id: str) -> dict:
    path = root / "candidates" / source_id / "upstream.json"
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RefreshError(f"unable to read candidate {source_id}: {exc}") from exc
    if not isinstance(content, dict):
        raise RefreshError(f"candidate {source_id} is not a JSON object")
    return content


def _serialize(config: dict) -> str:
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def promote_source(
    root: Path,
    source_id: str,
    regions: tuple[str, ...],
    mirror_func: Callable = mirror_files,
) -> list[str]:
    source = _source(root, source_id)
    if not source.enabled:
        raise RefreshError(f"source is disabled: {source_id}")
    if not regions or any(region not in source.regions for region in regions):
        raise RefreshError(f"source {source_id} does not support requested regions")

    candidate = _candidate(root, source_id)
    built: dict[str, dict] = {}
    cn_build: BuildResult | None = None
    for region in regions:
        if region == "us":
            built[region] = build_us(candidate)
        elif region == "cn":
            cn_build = build_cn(candidate, GITEE_RAW_BASE)
            built[region] = cn_build.config
        else:
            raise RefreshError(f"unsupported region: {region}")

    errors: list[str] = []
    for region, config in built.items():
        errors.extend(
            f"{region}:{finding.code}:{finding.path}"
            for finding in validate_config(config, region)
            if finding.severity == "error"
        )
    if errors:
        raise RefreshError("validation failed: " + ", ".join(errors))

    if cn_build is not None:
        try:
            mirror_func(cn_build.mirrors, root)
        except Exception as exc:
            raise RefreshError(f"dependency mirroring failed: {exc}") from exc

    stable_dir = root / "stable"
    stable_dir.mkdir(parents=True, exist_ok=True)
    temp_paths: dict[str, Path] = {}
    try:
        for region, config in built.items():
            temp = stable_dir / f"{region}.json.tmp"
            temp.write_text(_serialize(config), encoding="utf-8", newline="\n")
            parsed = json.loads(temp.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise RefreshError(f"serialized {region} configuration is not an object")
            temp_paths[region] = temp
        for region, temp in temp_paths.items():
            temp.replace(stable_dir / f"{region}.json")
    finally:
        for temp in temp_paths.values():
            temp.unlink(missing_ok=True)
    return list(built)


def _probe_urls(config: dict, region: str) -> tuple[list[str], list[Finding]]:
    urls: list[str] = []
    findings: list[Finding] = []

    def add(value: object):
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return
        if value.startswith("http://127.0.0.1"):
            return
        if region == "cn" and value.startswith(GITEE_RAW_BASE):
            findings.append(
                Finding(
                    "info",
                    "gitee-sync-pending",
                    "repository-owned Gitee URL requires the separately authorized Gitee sync",
                )
            )
            return
        if value not in urls:
            urls.append(value)

    add(config.get("spider"))
    for site in config.get("sites", []):
        if isinstance(site, dict):
            add(site.get("api"))
            add(site.get("ext"))
    for live in config.get("lives", []):
        if isinstance(live, dict):
            add(live.get("url"))
    return urls, findings


def _probe_with_retry(prober: Callable[[str], ProbeResult], url: str) -> ProbeResult:
    result = prober(url)
    if not result.ok and (result.status_code == 0 or result.status_code >= 500):
        return prober(url)
    return result


def verify_regions(
    root: Path,
    regions: tuple[str, ...],
    network: bool = False,
    probe_origin: str = "local-static-validation",
    prober: Callable[[str], ProbeResult] = probe_http,
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for region in regions:
        path = root / "stable" / f"{region}.json"
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RefreshError(f"unable to read stable {region}: {exc}") from exc
        findings = validate_config(config, region)
        probes: list[ProbeResult] = []
        if network:
            urls, pending = _probe_urls(config, region)
            findings.extend(pending)
            probes = [_probe_with_retry(prober, url) for url in urls]
        health_path = root / "health" / f"{region}.json"
        write_health_report(region, findings, probes, health_path, probe_origin)
        report = json.loads(health_path.read_text(encoding="utf-8"))
        statuses[region] = report["status"]
    return statuses
