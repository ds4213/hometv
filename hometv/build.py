from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import urllib.error
import urllib.request

from .curation import (
    CuratedSource,
    merge_curated_sites,
    parse_spider_reference,
    select_curated_sites,
)


MAX_MIRROR_BYTES = 25 * 1024 * 1024
USER_AGENT = "HomeTV-Config-Manager/1.0"

NITAN_SPIDER = "https://github.com/nitan-tv/nitan/raw/refs/heads/main/awdm.png"
NITAN_DOUBAN = "https://github.com/nitan-tv/nitan/raw/refs/heads/main/db.aowu"
NITAN_JINPAI = "https://github.com/nitan-tv/nitan/raw/refs/heads/main/py/py_jinpai.py"
KIMENTANM = "https://raw.githubusercontent.com/Kimentanm/aptv/refs/heads/master/m3u/iptv.m3u"
MIGU = "https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt"
YANG_GATHER = "https://iptv.yang-1989.eu.org/m3u/Gather.m3u"
YANG_SPORT = "https://iptv.yang-1989.eu.org/m3u/Sport.m3u"

ASSET_PATHS = {
    NITAN_SPIDER: "vendor/nitan/awdm.png",
    NITAN_DOUBAN: "vendor/nitan/db.aowu",
    NITAN_JINPAI: "vendor/nitan/py/py_jinpai.py",
    KIMENTANM: "vendor/live/kimentanm.m3u",
    MIGU: "vendor/live/migu.txt",
    YANG_GATHER: "vendor/live/yang-gather.m3u",
    YANG_SPORT: "vendor/live/yang-sport.m3u",
}

# Confirmed unusable on 2026-08-16: both YanG endpoints return HTTP 404 and
# the Migu list contains only an EXTM3U header with no channels.
OMIT_LIVE_URLS = {MIGU, YANG_GATHER, YANG_SPORT}

MAINLAND_DOH = [
    {
        "name": "AliDNS",
        "url": "https://dns.alidns.com/dns-query",
        "ips": ["223.5.5.5", "223.6.6.6"],
    },
    {
        "name": "DNSPod",
        "url": "https://doh.pub/dns-query",
        "ips": ["1.12.12.12", "120.53.53.53"],
    },
]


class BuildError(RuntimeError):
    """Raised when a regional build or mirror operation is unsafe."""


@dataclass(frozen=True)
class MirrorRequest:
    source_url: str
    repository_path: str
    expected_md5: str = ""


@dataclass(frozen=True)
class BuildResult:
    config: dict
    mirrors: tuple[MirrorRequest, ...]


def build_us(config: dict) -> dict:
    result = deepcopy(config)
    lives = result.get("lives", [])
    if isinstance(lives, list):
        lives[:] = [
            live
            for live in lives
            if not (isinstance(live, dict) and live.get("url") in OMIT_LIVE_URLS)
        ]
    return result


def _target(gitee_base: str, repository_path: str) -> str:
    return f"{gitee_base.rstrip('/')}/{repository_path}"


def build_cn(config: dict, gitee_base: str) -> BuildResult:
    result = deepcopy(config)
    mirrors: dict[str, MirrorRequest] = {}

    def rewrite(url: object) -> object:
        if not isinstance(url, str) or url not in ASSET_PATHS:
            return url
        repository_path = ASSET_PATHS[url]
        mirrors[repository_path] = MirrorRequest(url, repository_path)
        return _target(gitee_base, repository_path)

    result["spider"] = rewrite(result.get("spider"))
    sites = result.get("sites", [])
    if isinstance(sites, list):
        for site in sites:
            if not isinstance(site, dict):
                continue
            if "api" in site:
                site["api"] = rewrite(site["api"])
            if "ext" in site:
                site["ext"] = rewrite(site["ext"])

    lives = result.get("lives", [])
    if isinstance(lives, list):
        lives[:] = [
            live
            for live in lives
            if not (isinstance(live, dict) and live.get("url") in OMIT_LIVE_URLS)
        ]
        for live in lives:
            if isinstance(live, dict) and "url" in live:
                live["url"] = rewrite(live["url"])

    result["wallpaper"] = ""
    result["doh"] = deepcopy(MAINLAND_DOH)
    return BuildResult(config=result, mirrors=tuple(mirrors.values()))


def build_curated_vod(
    nitan: dict,
    wanger: dict,
    policy: CuratedSource,
    region: str,
    github_base: str,
    gitee_base: str,
) -> BuildResult:
    if region == "us":
        base = BuildResult(config=build_us(nitan), mirrors=())
        regional_base = github_base
    elif region == "cn":
        base = build_cn(nitan, gitee_base)
        regional_base = gitee_base
    else:
        raise BuildError(f"unsupported region: {region}")

    source_url, _algorithm, digest = parse_spider_reference(wanger.get("spider"))
    repository_path = "vendor/wanger/spider.jpg"
    jar = f"{_target(regional_base, repository_path)};md5;{digest}"
    selected = select_curated_sites(wanger, policy, jar)
    return BuildResult(
        config=merge_curated_sites(base.config, selected),
        mirrors=base.mirrors + (MirrorRequest(source_url, repository_path, digest),),
    )


def _safe_path(root: Path, repository_path: str) -> Path:
    relative = PurePosixPath(repository_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise BuildError(f"unsafe mirror path: {repository_path}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise BuildError(f"unsafe mirror path: {repository_path}")
    return path


def _is_html(raw: bytes, content_type: str) -> bool:
    prefix = raw.lstrip()[:256].lower()
    return "html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html"))


def mirror_files(
    requests: tuple[MirrorRequest, ...], root: Path, timeout: float = 30.0
) -> dict:
    records: list[dict] = []
    for item in requests:
        destination = _safe_path(root, item.repository_path)
        request = urllib.request.Request(item.source_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise BuildError(f"{item.source_url}: HTTP {status}")
                raw = response.read(MAX_MIRROR_BYTES + 1)
                content_type = response.headers.get_content_type()
        except BuildError:
            raise
        except (OSError, urllib.error.URLError) as exc:
            raise BuildError(f"{item.source_url}: mirror request failed: {exc}") from exc

        if not raw:
            raise BuildError(f"{item.source_url}: empty mirror response")
        if len(raw) > MAX_MIRROR_BYTES:
            raise BuildError(f"{item.source_url}: mirror exceeds 25 MiB")
        if _is_html(raw, content_type):
            raise BuildError(f"{item.source_url}: mirror response is HTML")

        md5 = ""
        if item.expected_md5:
            md5 = hashlib.md5(raw).hexdigest()
            if md5 != item.expected_md5.lower():
                raise BuildError(f"{item.source_url}: MD5 mismatch")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_name(destination.name + ".tmp")
        try:
            temp_path.write_bytes(raw)
            temp_path.replace(destination)
        finally:
            temp_path.unlink(missing_ok=True)
        records.append(
            {
                "source_url": item.source_url,
                "path": item.repository_path,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        if item.expected_md5:
            records[-1]["expected_md5"] = item.expected_md5
            records[-1]["md5"] = md5

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }
    manifest_path = root / "vendor" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_temp = manifest_path.with_name("manifest.json.tmp")
    try:
        manifest_temp.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest_temp.replace(manifest_path)
    finally:
        manifest_temp.unlink(missing_ok=True)
    return manifest
