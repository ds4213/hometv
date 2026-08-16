"""Declarative selection of the approved Wang source sites."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CurationError(RuntimeError):
    """Raised when a curation policy or source set is invalid."""


@dataclass(frozen=True)
class CuratedSource:
    source_id: str
    name_prefix: str
    keys: tuple[str, ...]


def load_curated_source(path: Path) -> CuratedSource:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CurationError(f"invalid curated source: {path}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise CurationError("unsupported curated source schema")
    source_id = data.get("source_id")
    prefix = data.get("name_prefix")
    keys = data.get("keys")
    if not isinstance(source_id, str) or not source_id:
        raise CurationError("source_id must be a non-empty string")
    if not isinstance(prefix, str) or not prefix:
        raise CurationError("name_prefix must be a non-empty string")
    if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
        raise CurationError("keys must be a list of strings")
    if len(keys) != len(set(keys)):
        raise CurationError("duplicate curated key")
    return CuratedSource(source_id, prefix, tuple(keys))


_SPIDER_REFERENCE = re.compile(r"^(https?://[^;]+);(md5);([0-9a-fA-F]{32})$")


def parse_spider_reference(reference: str) -> tuple[str, str, str]:
    if not isinstance(reference, str):
        raise CurationError("invalid spider reference")
    match = _SPIDER_REFERENCE.fullmatch(reference)
    if match is None:
        raise CurationError("invalid spider reference")
    return match.group(1), match.group(2), match.group(3)


def select_curated_sites(config: dict, policy: CuratedSource, jar: str) -> list[dict]:
    sites = config.get("sites") if isinstance(config, dict) else None
    if not isinstance(sites, list):
        raise CurationError("upstream sites must be a list")
    indexed: dict[Any, dict] = {}
    for site in sites:
        if not isinstance(site, dict) or "key" not in site:
            raise CurationError("upstream site must have a key")
        key = site["key"]
        if key in indexed:
            raise CurationError(f"duplicate upstream key: {key}")
        indexed[key] = site
    missing = [key for key in policy.keys if key not in indexed]
    if missing:
        raise CurationError(f"missing curated keys: {', '.join(missing)}")
    selected: list[dict] = []
    approved = set(policy.keys)
    for source in sites:
        if source["key"] not in approved:
            continue
        if source.get("type") != 3:
            raise CurationError(f"curated site is not type 3: {source['key']}")
        site = copy.deepcopy(source)
        original_name = site.get("name")
        if not isinstance(original_name, str):
            raise CurationError(f"curated site missing name: {source['key']}")
        site["name"] = policy.name_prefix + original_name
        site["jar"] = jar
        selected.append(site)
    return selected


def merge_curated_sites(base: dict, selected: list[dict]) -> dict:
    merged = copy.deepcopy(base)
    base_sites = merged.get("sites")
    if not isinstance(base_sites, list):
        raise CurationError("base sites must be a list")
    existing = {site.get("key") for site in base_sites if isinstance(site, dict)}
    added: set[Any] = set()
    for site in selected:
        if not isinstance(site, dict) or "key" not in site:
            raise CurationError("curated site must have a key")
        key = site["key"]
        if key in existing or key in added:
            raise CurationError(f"site key collision: {key}")
        added.add(key)
    merged["sites"].extend(copy.deepcopy(selected))
    return merged
