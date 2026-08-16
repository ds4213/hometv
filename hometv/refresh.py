from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse

from hometv.build import (
    BuildError,
    BuildResult,
    build_cn,
    build_curated_vod,
    build_live_config,
    build_us,
    mirror_files,
)
from hometv.curation import (
    CurationError,
    load_curated_source,
    parse_spider_reference,
    select_curated_sites,
)
from hometv.fetch import FetchedConfig, FetchError, fetch_config, write_candidate
from hometv.live import PlaylistError, fetch_live_bytes, merge_playlists, validate_playlist
from hometv.registry import Source, load_registry
from hometv.validate import (
    Finding,
    ProbeResult,
    probe_http,
    validate_config,
    validate_live_config,
    write_health_report,
)


GITEE_RAW_BASE = "https://gitee.com/ds4213tv/hometv/raw/main"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/ds4213/hometv/main"
EVENT_PLAYLIST_URL = "http://82.156.243.185:33389/fwc.m3u"
COMPOSE_OUTPUTS = (
    "stable/us.json",
    "stable/cn.json",
    "stable/live-us.json",
    "stable/live-cn.json",
    "vendor/live/auto-us.m3u",
    "vendor/live/auto-cn.m3u",
)


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
            if source.id == "wangerxiao":
                policy = load_curated_source(root / "sources" / "wanger-curated.json")
                if policy.source_id != source.id:
                    raise RefreshError(
                        f"curation policy source does not match candidate: {source.id}"
                    )
                _spider_url, _algorithm, digest = parse_spider_reference(
                    fetched.content.get("spider")
                )
                jar = f"{GITEE_RAW_BASE}/vendor/wanger/spider.jpg;md5;{digest}"
                select_curated_sites(fetched.content, policy, jar)
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


def _validation_errors(findings: list[Finding], label: str) -> None:
    errors = [
        f"{finding.code}:{finding.path}"
        for finding in findings
        if finding.severity == "error"
    ]
    if errors:
        raise RefreshError(f"{label} validation failed: {', '.join(errors)}")


def _stage_json(
    stage: Path, relative: str, config: dict, region: str, live: bool = False
) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(config), encoding="utf-8", newline="\n")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RefreshError(f"unable to re-read staged {relative}: {exc}") from exc
    findings = validate_live_config(parsed, region) if live else validate_config(parsed, region)
    _validation_errors(findings, f"staged {relative}")


def _stage_playlist(stage: Path, relative: str, raw: bytes, region: str) -> None:
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    try:
        validate_playlist(path.read_bytes(), region)
    except (OSError, PlaylistError) as exc:
        raise RefreshError(f"unable to validate staged {relative}: {exc}") from exc


def _replace_staged_outputs(root: Path, stage: Path) -> None:
    previous = {
        relative: (root / relative).read_bytes() if (root / relative).exists() else None
        for relative in COMPOSE_OUTPUTS
    }
    replaced: list[str] = []
    try:
        for relative in COMPOSE_OUTPUTS:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / relative, destination)
            replaced.append(relative)
    except OSError as exc:
        for relative in reversed(replaced):
            destination = root / relative
            raw = previous[relative]
            if raw is None:
                destination.unlink(missing_ok=True)
                continue
            rollback = stage / "rollback" / relative
            rollback.parent.mkdir(parents=True, exist_ok=True)
            rollback.write_bytes(raw)
            os.replace(rollback, destination)
        raise RefreshError(f"unable to replace composed outputs: {exc}") from exc


def _event_playlist(event_fetcher: Callable[[str], bytes]) -> bytes | None:
    try:
        return event_fetcher(EVENT_PLAYLIST_URL)
    except urllib.error.HTTPError:
        return None
    except urllib.error.URLError as exc:
        if _is_expected_network_error(exc):
            return None
        raise
    except (ConnectionError, TimeoutError):
        return None
    except PlaylistError as exc:
        if _is_expected_network_error(exc.__cause__):
            return None
        raise


def _is_expected_network_error(error: BaseException | None) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return True
    if isinstance(error, urllib.error.URLError):
        return not isinstance(error.reason, (PermissionError, FileNotFoundError))
    return isinstance(error, (ConnectionError, TimeoutError))


def _http_playlist_entries(raw: bytes) -> bytes:
    """Drop non-HTTP entries from a checked-in seed before strict playlist validation."""
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise RefreshError("Kimentanm seed must be UTF-8") from exc
    accepted: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip().startswith("#EXTINF"):
            accepted.append(line)
            index += 1
            continue
        entry = [line]
        index += 1
        while index < len(lines) and not lines[index].strip():
            entry.append(lines[index])
            index += 1
        if index >= len(lines):
            raise RefreshError("Kimentanm seed has #EXTINF without a media URL")
        url = lines[index].strip()
        index += 1
        if url.startswith(("http://", "https://")):
            accepted.extend(entry)
            accepted.append(url)
    return ("\n".join(accepted) + "\n").encode("utf-8")


def compose_stable(
    root: Path,
    mirror_func: Callable = mirror_files,
    event_fetcher: Callable[[str], bytes] = fetch_live_bytes,
) -> list[str]:
    """Compose and atomically replace regional VOD, live-config, and auto-live outputs."""
    try:
        sources = {
            source.id: source
            for source in load_registry(root / "sources" / "registry.json")
        }
        if not sources.get("nitan-dm") or not sources.get("wangerxiao"):
            raise RefreshError("registry must include nitan-dm and wangerxiao")
        policy = load_curated_source(root / "sources" / "wanger-curated.json")
        if policy.source_id != "wangerxiao":
            raise RefreshError("curation policy must target wangerxiao")
        nitan = _candidate(root, "nitan-dm")
        wanger = _candidate(root, "wangerxiao")
        vod = {
            region: build_curated_vod(
                nitan, wanger, policy, region, GITHUB_RAW_BASE, GITEE_RAW_BASE
            )
            for region in ("us", "cn")
        }
        live = {
            region: build_live_config(region, GITHUB_RAW_BASE, GITEE_RAW_BASE)
            for region in ("us", "cn")
        }
    except (BuildError, CurationError) as exc:
        raise RefreshError(str(exc)) from exc

    for region in ("us", "cn"):
        _validation_errors(validate_config(vod[region].config, region), f"{region} VOD")
        _validation_errors(validate_live_config(live[region], region), f"{region} live config")

    mirrors = tuple(request for region in ("us", "cn") for request in vod[region].mirrors)
    try:
        mirror_func(mirrors, root)
    except (BuildError, OSError, urllib.error.URLError) as exc:
        raise RefreshError(f"dependency mirroring failed: {exc}") from exc

    seed = _http_playlist_entries((root / "vendor" / "live" / "kimentanm.m3u").read_bytes())
    event = _event_playlist(event_fetcher)
    playlists: dict[str, bytes] = {}
    for region in ("us", "cn"):
        raw = merge_playlists([seed] + ([event] if event is not None else []))
        destination = root / "vendor" / "live" / f"auto-{region}.m3u"
        previous = destination.read_bytes() if destination.exists() else None
        try:
            validate_playlist(raw, region, previous=previous)
        except PlaylistError as exc:
            raise RefreshError(f"{region} automatic playlist validation failed: {exc}") from exc
        playlists[region] = raw

    with tempfile.TemporaryDirectory(prefix=".compose-", dir=root) as directory:
        stage = Path(directory)
        _stage_json(stage, "stable/us.json", vod["us"].config, "us")
        _stage_json(stage, "stable/cn.json", vod["cn"].config, "cn")
        _stage_json(stage, "stable/live-us.json", live["us"], "us", live=True)
        _stage_json(stage, "stable/live-cn.json", live["cn"], "cn", live=True)
        _stage_playlist(stage, "vendor/live/auto-us.m3u", playlists["us"], "us")
        _stage_playlist(stage, "vendor/live/auto-cn.m3u", playlists["cn"], "cn")
        _replace_staged_outputs(root, stage)

    return list(COMPOSE_OUTPUTS[:4])


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


def _without_checksum(value: str) -> str:
    marker = value.lower().find(";md5;")
    return value[:marker] if marker >= 0 else value


def _normalized_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate.lower().startswith(("http://", "https://")):
        return None
    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, "")
    )


def _nested_url_values(value: object, path: str, epg: bool = False) -> list[tuple[str, str]]:
    if isinstance(value, str):
        values = value.split(",") if epg else [value]
        return [
            (item.strip(), f"{path}[{index}]") if epg else (item.strip(), path)
            for index, item in enumerate(values)
            if item.strip()
        ]
    if isinstance(value, list):
        return [
            candidate
            for index, item in enumerate(value)
            for candidate in _nested_url_values(item, f"{path}[{index}]")
        ]
    if isinstance(value, dict):
        return [
            candidate
            for key, item in value.items()
            for candidate in _nested_url_values(
                item, f"{path}.{key}", epg=str(key).casefold() == "epg"
            )
        ]
    return []


def _probe_url_values(config: dict) -> list[tuple[str, str]]:
    if not isinstance(config, dict):
        return []
    values: list[tuple[str, str]] = []

    def add(value: object, path: str, checksum: bool = False) -> None:
        if isinstance(value, str):
            values.append((_without_checksum(value) if checksum else value, path))

    add(config.get("spider"), "$.spider", checksum=True)
    add(config.get("wallpaper"), "$.wallpaper")
    for index, site in enumerate(config.get("sites", [])):
        if not isinstance(site, dict):
            continue
        path = f"$.sites[{index}]"
        add(site.get("api"), f"{path}.api")
        add(site.get("jar"), f"{path}.jar", checksum=True)
        values.extend(_nested_url_values(site.get("ext"), f"{path}.ext"))
    values.extend(_nested_url_values(config.get("doh"), "$.doh"))
    values.extend(_nested_url_values(config.get("lives"), "$.lives"))
    return values


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
        vod_path = root / "stable" / f"{region}.json"
        live_path = root / "stable" / f"live-{region}.json"
        try:
            vod = json.loads(vod_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RefreshError(f"unable to read stable {region}: {exc}") from exc
        try:
            live = json.loads(live_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RefreshError(f"unable to read stable live-{region}: {exc}") from exc
        findings = validate_config(vod, region) + validate_live_config(live, region)
        probes: list[ProbeResult] = []
        if network:
            urls: list[str] = []
            seen: set[str] = set()
            for config in (vod, live):
                for value, path in _probe_url_values(config):
                    url = _normalized_http_url(value)
                    if url is None or url in seen:
                        continue
                    seen.add(url)
                    host = urllib.parse.urlsplit(url).hostname
                    if host == "127.0.0.1":
                        continue
                    if region == "cn" and url.startswith(GITEE_RAW_BASE):
                        findings.append(
                            Finding(
                                "info",
                                "gitee-sync-pending",
                                "repository-owned Gitee URL requires the separately authorized Gitee sync",
                                path,
                            )
                        )
                        continue
                    urls.append(url)
            probes = [_probe_with_retry(prober, url) for url in urls]
        health_path = root / "health" / f"{region}.json"
        write_health_report(region, findings, probes, health_path, probe_origin)
        report = json.loads(health_path.read_text(encoding="utf-8"))
        statuses[region] = report["status"]
    return statuses
