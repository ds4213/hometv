"""Safe parsing, validation, and publication of M3U live playlists."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request
import urllib.request


MAX_LIVE_BYTES = 25 * 1024 * 1024
SENSITIVE_QUERY_KEYS = {
    "token",
    "access_token",
    "auth",
    "authorization",
    "password",
    "passwd",
    "secret",
    "signature",
    "sig",
}
GROUP_TITLE = re.compile(r'''\bgroup-title\s*=\s*["']([^"']*)["']''', re.IGNORECASE)


class PlaylistError(RuntimeError):
    """Raised when a live playlist is malformed or unsafe to publish."""


@dataclass(frozen=True)
class M3UEntry:
    info: str
    name: str
    url: str
    group: str


@dataclass(frozen=True)
class PlaylistReport:
    profile: str
    channel_count: int
    url_count: int
    groups: tuple[str, ...]
    sha256: str


def _is_html(raw: bytes) -> bool:
    prefix = raw.lstrip().lower()
    return prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html")


def parse_m3u(raw: bytes) -> tuple[str, list[M3UEntry]]:
    """Parse a UTF-8 M3U playlist while rejecting ambiguous structure."""
    if _is_html(raw):
        raise PlaylistError("HTML response is not an M3U playlist")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise PlaylistError("playlist must be UTF-8") from error

    lines = [line.strip() for line in text.splitlines()]
    nonempty = [(index, line) for index, line in enumerate(lines) if line]
    if not nonempty or not nonempty[0][1].startswith("#EXTM3U"):
        raise PlaylistError("playlist must start with #EXTM3U")
    header_index, header = nonempty[0]
    entries: list[M3UEntry] = []
    index = header_index + 1
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line.startswith("#EXTINF"):
            if "," not in line:
                raise PlaylistError("#EXTINF is missing a channel name")
            info, name = line.rsplit(",", 1)
            name = name.strip()
            if not name:
                raise PlaylistError("empty channel name")
            index += 1
            while index < len(lines) and not lines[index]:
                index += 1
            if index >= len(lines):
                raise PlaylistError("#EXTINF is missing a media URL")
            url = lines[index]
            if _is_html(url.encode("utf-8")):
                raise PlaylistError("HTML response is not a media URL")
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise PlaylistError("media URL must use HTTP(S)")
            group_match = GROUP_TITLE.search(info)
            group = group_match.group(1) if group_match else ""
            entries.append(M3UEntry(info=info, name=name, url=url, group=group))
            index += 1
            continue
        if not line.startswith("#"):
            raise PlaylistError("orphan URL without #EXTINF")
        index += 1
    return header, entries


def serialize_m3u(header: str, entries: list[M3UEntry]) -> bytes:
    """Serialize entries with normalized newlines and one terminal newline."""
    lines = [header.strip()]
    for entry in entries:
        lines.extend((f"{entry.info},{entry.name}", entry.url))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.username is not None or parsed.password is not None:
        raise PlaylistError("URL userinfo is not allowed")
    hostname = parsed.hostname
    if hostname is None:
        raise PlaylistError("media URL must include a hostname")
    normalized_host = hostname.casefold().rstrip(".")
    if normalized_host.endswith((".local", ".lan")):
        raise PlaylistError("local hostname is not allowed")
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError:
        pass
    else:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise PlaylistError("private address is not allowed")
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in SENSITIVE_QUERY_KEYS and value:
            raise PlaylistError("sensitive query parameter is not allowed")


def validate_playlist(
    raw: bytes, profile: str, previous: bytes | None = None
) -> PlaylistReport:
    """Validate a playlist's contents and return a stable health report."""
    _header, entries = parse_m3u(raw)
    names = {entry.name.strip().casefold() for entry in entries}
    urls = {entry.url for entry in entries}
    if len(names) < 20:
        raise PlaylistError("playlist must contain at least 20 channels")

    pairs: set[tuple[str, str]] = set()
    for entry in entries:
        pair = (entry.name.strip().casefold(), entry.url)
        if pair in pairs:
            raise PlaylistError("duplicate channel/URL pair")
        pairs.add(pair)
        _validate_url(entry.url)

    if previous is not None:
        try:
            previous_report = validate_playlist(previous, profile)
        except PlaylistError:
            previous_report = None
        if (
            previous_report is not None
            and (previous_report.channel_count - len(names)) / previous_report.channel_count > 0.35
        ):
            raise PlaylistError("channel drop exceeds 35%")

    if profile.casefold() == "cn":
        if not any(entry.name.casefold().startswith("cctv") for entry in entries):
            raise PlaylistError("CN playlist requires a CCTV channel")
        if not any("卫视" in entry.name or "卫视" in entry.group for entry in entries):
            raise PlaylistError("CN playlist requires a 卫视 channel or group")

    groups = tuple(sorted({entry.group for entry in entries if entry.group}))
    return PlaylistReport(
        profile=profile,
        channel_count=len(names),
        url_count=len(urls),
        groups=groups,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def merge_playlists(raw_items: list[bytes]) -> bytes:
    """Merge parsed playlists, retaining first-seen channel and URL pairs."""
    if not raw_items:
        raise PlaylistError("at least one playlist is required")
    header, first_entries = parse_m3u(raw_items[0])
    entries = list(first_entries)
    seen = {(entry.name, entry.url) for entry in entries}
    for raw in raw_items[1:]:
        _ignored_header, source_entries = parse_m3u(raw)
        for entry in source_entries:
            pair = (entry.name, entry.url)
            if pair not in seen:
                seen.add(pair)
                entries.append(entry)
    return serialize_m3u(header, entries)


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _health_payload(report: PlaylistReport | None, profile: str, status: str, error: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "status": status,
    }
    if report is not None:
        payload.update(
            {
                "channel_count": report.channel_count,
                "url_count": report.url_count,
                "groups": report.groups,
                "sha256": report.sha256,
            }
        )
    if error is not None:
        payload["error"] = error
    return payload


def publish_playlist(
    raw: bytes, destination: Path, profile: str, health_path: Path
) -> PlaylistReport:
    """Validate and atomically publish a live playlist and its health record."""
    previous = destination.read_bytes() if destination.exists() else None
    try:
        report = validate_playlist(raw, profile, previous)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_bytes(raw)
        parse_m3u(temporary.read_bytes())
        os.replace(temporary, destination)
    except PlaylistError as error:
        _atomic_json_write(
            health_path,
            _health_payload(None, profile, "rejected", str(error)),
        )
        raise
    _atomic_json_write(health_path, _health_payload(report, profile, "accepted"))
    return report


def fetch_live_bytes(url: str, timeout: float = 20.0) -> bytes:
    """Fetch a bounded live playlist without exposing URL query values in errors."""
    request = Request(url, headers={"User-Agent": "okhttp/4.12.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise PlaylistError(f"live playlist returned HTTP {response.status}")
            raw = response.read(MAX_LIVE_BYTES + 1)
    except PlaylistError:
        raise
    except HTTPError as error:
        raise PlaylistError(f"live playlist returned HTTP {error.code}") from error
    except (OSError, URLError) as error:
        raise PlaylistError("live playlist request failed") from error
    if not raw:
        raise PlaylistError("live playlist response is empty")
    if len(raw) > MAX_LIVE_BYTES:
        raise PlaylistError("live playlist response exceeds 25 MiB")
    if _is_html(raw):
        raise PlaylistError("HTML response is not a live playlist")
    return raw
