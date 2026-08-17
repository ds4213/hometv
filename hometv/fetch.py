from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from hometv.registry import Source


MAX_CONFIG_BYTES = 10 * 1024 * 1024
USER_AGENT = "HomeTV-Config-Manager/1.0"


class FetchError(RuntimeError):
    """Raised when an upstream response is not a usable FongMi configuration."""


@dataclass(frozen=True)
class FetchedConfig:
    source: Source
    content: dict
    raw: bytes
    fetched_at: str
    sha256: str


def _looks_like_html(raw: bytes, content_type: str) -> bool:
    prefix = raw.lstrip()[:256].lower()
    return "html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html"))


def _idna_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.hostname is None:
        return url
    hostname = parts.hostname.encode("idna").decode("ascii")
    netloc = hostname
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    return urllib.parse.urlunsplit(parts._replace(netloc=netloc))


def fetch_config(source: Source, timeout: float = 20.0) -> FetchedConfig:
    request = urllib.request.Request(_idna_url(source.url), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise FetchError(f"{source.id}: HTTP {status}")
            raw = response.read(MAX_CONFIG_BYTES + 1)
            content_type = response.headers.get_content_type()
    except FetchError:
        raise
    except (OSError, urllib.error.URLError) as exc:
        raise FetchError(f"{source.id}: request failed: {exc}") from exc

    if len(raw) > MAX_CONFIG_BYTES:
        raise FetchError(f"{source.id}: response exceeds 10 MiB")
    if not raw:
        raise FetchError(f"{source.id}: empty response")
    if _looks_like_html(raw, content_type):
        raise FetchError(f"{source.id}: response is HTML, not configuration JSON")

    try:
        text = raw.decode("utf-8-sig")
        content = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError(f"{source.id}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(content, dict):
        raise FetchError(f"{source.id}: configuration must be a top-level JSON object")

    return FetchedConfig(
        source=source,
        content=content,
        raw=raw,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def write_candidate(fetched: FetchedConfig, root: Path) -> Path:
    candidate_dir = root / fetched.source.id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    config_path = candidate_dir / "upstream.json"
    config_temp = candidate_dir / "upstream.json.tmp"
    metadata_path = candidate_dir / "metadata.json"
    metadata_temp = candidate_dir / "metadata.json.tmp"

    try:
        serialized = json.dumps(fetched.content, ensure_ascii=False, indent=2) + "\n"
        config_temp.write_text(serialized, encoding="utf-8", newline="\n")
        parsed = json.loads(config_temp.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise FetchError("candidate validation did not produce an object")
        config_temp.replace(config_path)

        metadata = {
            "source_id": fetched.source.id,
            "source_name": fetched.source.name,
            "source_url": fetched.source.url,
            "fetched_at": fetched.fetched_at,
            "sha256": fetched.sha256,
            "bytes": len(fetched.raw),
        }
        metadata_temp.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        metadata_temp.replace(metadata_path)
    finally:
        config_temp.unlink(missing_ok=True)
        metadata_temp.unlink(missing_ok=True)
    return config_path
