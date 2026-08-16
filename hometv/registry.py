from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


VALID_REGIONS = {"us", "cn"}


class RegistryError(ValueError):
    """Raised when the source registry is malformed."""


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    regions: tuple[str, ...]
    enabled: bool
    stable_regions: tuple[str, ...]
    disabled_reason: str = ""


def _regions(value: object, field: str, source_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RegistryError(f"{source_id}: {field} must be a non-empty list")
    regions = tuple(value)
    if any(not isinstance(region, str) or region not in VALID_REGIONS for region in regions):
        raise RegistryError(f"{source_id}: {field} contains an unknown region")
    if len(regions) != len(set(regions)):
        raise RegistryError(f"{source_id}: {field} contains duplicates")
    return regions


def load_registry(path: Path) -> list[Source]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"unable to read registry: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise RegistryError("unsupported registry schema")
    records = payload.get("sources")
    if not isinstance(records, list):
        raise RegistryError("sources must be a list")

    result: list[Source] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise RegistryError("source records must be objects")
        source_id = record.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise RegistryError("source id must be a non-empty string")
        if source_id in seen:
            raise RegistryError(f"duplicate source id: {source_id}")
        seen.add(source_id)

        name = record.get("name")
        url = record.get("url")
        enabled = record.get("enabled")
        if not isinstance(name, str) or not name.strip():
            raise RegistryError(f"{source_id}: name must be a non-empty string")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise RegistryError(f"{source_id}: url must be HTTP(S)")
        if not isinstance(enabled, bool):
            raise RegistryError(f"{source_id}: enabled must be boolean")

        regions = _regions(record.get("regions"), "regions", source_id)
        stable_value = record.get("stable_regions", [])
        if not isinstance(stable_value, list):
            raise RegistryError(f"{source_id}: stable_regions must be a list")
        stable_regions = tuple(stable_value)
        if any(region not in VALID_REGIONS for region in stable_regions):
            raise RegistryError(f"{source_id}: stable_regions contains an unknown region")
        if any(region not in regions for region in stable_regions):
            raise RegistryError(f"{source_id}: stable_regions must be included in regions")
        if not enabled and stable_regions:
            raise RegistryError(f"{source_id}: a disabled source cannot be stable")

        disabled_reason = record.get("disabled_reason", "")
        if not isinstance(disabled_reason, str):
            raise RegistryError(f"{source_id}: disabled_reason must be a string")
        if not enabled and not disabled_reason.strip():
            raise RegistryError(f"{source_id}: disabled_reason is required")

        result.append(
            Source(
                id=source_id,
                name=name,
                url=url,
                regions=regions,
                enabled=enabled,
                stable_regions=stable_regions,
                disabled_reason=disabled_reason,
            )
        )
    return result
