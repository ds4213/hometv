"""Build the US-only VOD extension from a pinned, locally checked snapshot."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from .curation import CurationError, load_curated_source, select_curated_sites


def extend_us_vod(root: Path, base: dict, delivery_base: str) -> dict:
    policy_path = root / "sources" / "us-vod.json"
    if not policy_path.exists():
        return deepcopy(base)
    settings = json.loads(policy_path.read_text(encoding="utf-8"))
    policy = load_curated_source(policy_path)
    candidate = json.loads(
        (root / "candidates" / policy.source_id / "upstream.json").read_text(encoding="utf-8")
    )
    digest = settings["spider_md5"]
    if not candidate.get("spider", "").endswith(";md5;" + digest):
        raise CurationError("US snapshot and approved Spider digest differ")
    relative = f"vendor/qist/fan-{digest}.txt"
    raw = (root / relative).read_bytes()
    if hashlib.md5(raw).hexdigest() != digest:
        raise CurationError("US Spider MD5 mismatch")
    jar = f"{delivery_base.rstrip('/')}/{relative};md5;{digest}"
    selected = select_curated_sites(candidate, policy, jar)
    by_key = {site["key"]: site for site in selected}
    ordered = []
    snapshot_base = f"https://raw.githubusercontent.com/qist/tvbox/{settings['commit']}/"
    for key in policy.keys:
        site = by_key[key]
        site["key"] = "qist-fty:" + key
        site["name"] = policy.name_prefix + key
        site["quickSearch"] = int(key in settings["quick_search_keys"])
        # Cloud-drive authentication is not part of the parents' default setup.
        if isinstance(site.get("ext"), dict):
            site["ext"].pop("Cloud-drive", None)
        for field in ("api", "ext"):
            if isinstance(site.get(field), str) and site[field].startswith("./"):
                site[field] = urljoin(snapshot_base, site[field])
        ordered.append(site)
    result = deepcopy(base)
    # Retain all existing sites as selectable fallback, without searching them
    # automatically alongside the new defaults.
    for site in result["sites"]:
        site["quickSearch"] = 0
        site.setdefault("jar", result["spider"])
    result["sites"] = ordered + result["sites"]
    result["spider"] = jar
    return result
