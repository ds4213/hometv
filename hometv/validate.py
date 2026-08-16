from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Iterator
import urllib.error
import urllib.parse
import urllib.request


MAX_PROBE_BYTES = 4 * 1024 * 1024
USER_AGENT = "okhttp/4.12.0"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True)
class ProbeResult:
    target: str
    ok: bool
    status_code: int
    elapsed_ms: int
    bytes: int
    sha256: str
    content_type: str
    error: str
    media_target: str


def _strings(value: object, path: str = "$") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")


def validate_config(config: dict, region: str) -> list[Finding]:
    findings: list[Finding] = []
    if region not in {"us", "cn"}:
        return [Finding("error", "invalid-region", f"unsupported region: {region}")]
    if not isinstance(config, dict):
        return [Finding("error", "invalid-config", "configuration must be an object")]

    spider = config.get("spider")
    if not isinstance(spider, str) or not spider:
        findings.append(Finding("error", "invalid-spider", "spider must be a non-empty string", "$.spider"))

    sites = config.get("sites")
    if not isinstance(sites, list):
        findings.append(Finding("error", "invalid-sites", "sites must be a list", "$.sites"))
    else:
        seen: set[str] = set()
        for index, site in enumerate(sites):
            if not isinstance(site, dict):
                findings.append(
                    Finding("error", "invalid-site", "site must be an object", f"$.sites[{index}]")
                )
                continue
            key = site.get("key")
            if isinstance(key, str) and key:
                if key in seen:
                    findings.append(
                        Finding(
                            "error",
                            "duplicate-site-key",
                            f"duplicate site key: {key}",
                            f"$.sites[{index}].key",
                        )
                    )
                seen.add(key)

    if not isinstance(config.get("lives", []), list):
        findings.append(Finding("error", "invalid-lives", "lives must be a list", "$.lives"))

    for path, value in _strings(config):
        if not value.startswith(("http://", "https://")):
            continue
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "http" and host not in {"127.0.0.1", "localhost"}:
            findings.append(
                Finding("warning", "cleartext-http", "cleartext HTTP dependency", path)
            )
        if region == "cn" and (
            host == "github.com"
            or host.endswith(".github.com")
            or host == "raw.githubusercontent.com"
        ):
            findings.append(
                Finding(
                    "error",
                    "mainland-github-url",
                    "mainland configuration contains a GitHub dependency",
                    path,
                )
            )
    return findings


def _sanitize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc.rsplit("@", 1)[-1]
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def _request(url: str, timeout: float, byte_range: bool = False) -> tuple[int, bytes, str, int]:
    headers = {"User-Agent": USER_AGENT}
    if byte_range:
        headers["Range"] = "bytes=0-65535"
    request = urllib.request.Request(url, headers=headers)
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        raw = response.read(MAX_PROBE_BYTES + 1)
        content_type = response.headers.get_content_type()
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if len(raw) > MAX_PROBE_BYTES:
        raise ValueError("response exceeds 4 MiB probe limit")
    return status, raw, content_type, elapsed_ms


def _html(raw: bytes, content_type: str) -> bool:
    prefix = raw.lstrip()[:256].lower()
    return "html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html"))


def _playlist_targets(raw: bytes, base_url: str, limit: int = 25) -> list[str]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    targets: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            target = urllib.parse.urljoin(base_url, value)
            if target not in targets:
                targets.append(target)
            if len(targets) >= limit:
                break
    return targets


def probe_http(url: str, timeout: float = 15.0) -> ProbeResult:
    target = _sanitize_url(url)
    try:
        status, raw, content_type, elapsed_ms = _request(url, timeout)
        if status < 200 or status >= 300:
            raise ValueError(f"HTTP {status}")
        if not raw:
            raise ValueError("empty response")
        if _html(raw, content_type):
            raise ValueError("response is HTML")

        is_playlist = (
            urllib.parse.urlsplit(url).path.lower().endswith((".m3u", ".m3u8"))
            or "mpegurl" in content_type.lower()
            or raw.lstrip().startswith(b"#EXTM3U")
        )
        if is_playlist:
            media_urls = _playlist_targets(raw, url)
            if not media_urls:
                raise ValueError("playlist has no playable resource")
            last_error = ""
            for media_url in media_urls:
                try:
                    media_status, media, media_type, media_ms = _request(
                        media_url, timeout, byte_range=True
                    )
                    if media_status < 200 or media_status >= 300:
                        raise ValueError(f"media HTTP {media_status}")
                    if not media or _html(media, media_type):
                        raise ValueError("media resource is empty or HTML")
                    return ProbeResult(
                        target=target,
                        ok=True,
                        status_code=media_status,
                        elapsed_ms=elapsed_ms + media_ms,
                        bytes=len(media),
                        sha256=hashlib.sha256(media).hexdigest(),
                        content_type=media_type,
                        error="",
                        media_target=_sanitize_url(media_url),
                    )
                except urllib.error.HTTPError as exc:
                    last_error = f"HTTP {exc.code}"
                except (OSError, urllib.error.URLError, ValueError) as exc:
                    last_error = str(exc)
            raise ValueError(f"no playable sample in first {len(media_urls)} entries: {last_error}")

        return ProbeResult(
            target=target,
            ok=True,
            status_code=status,
            elapsed_ms=elapsed_ms,
            bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            content_type=content_type,
            error="",
            media_target="",
        )
    except urllib.error.HTTPError as exc:
        return ProbeResult(target, False, exc.code, 0, 0, "", "", f"HTTP {exc.code}", "")
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return ProbeResult(target, False, 0, 0, 0, "", "", str(exc), "")


def write_health_report(
    region: str,
    findings: list[Finding],
    probes: list[ProbeResult],
    path: Path,
    probe_origin: str,
) -> None:
    has_error = any(item.severity == "error" for item in findings) or any(
        not probe.ok for probe in probes
    )
    has_warning = any(item.severity == "warning" for item in findings)
    status = "error" if has_error else "warning" if has_warning else "ok"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "probe_origin": probe_origin,
        "status": status,
        "findings": [asdict(item) for item in findings],
        "probes": [asdict(item) for item in probes],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
