from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from hometv.live import PlaylistError, publish_playlist
from hometv.refresh import compose_stable, promote_source, refresh_candidates, verify_regions


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Manage HomeTV FongMi configurations")
    command.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("candidates", help="refresh enabled candidate sources")
    subcommands.add_parser("compose", help="compose all regional stable artifacts")

    promote = subcommands.add_parser("promote", help="promote a verified candidate")
    promote.add_argument("--source", required=True)
    promote.add_argument("--regions", choices=("us", "cn"), nargs="+", required=True)

    verify = subcommands.add_parser("verify", help="validate stable configurations")
    verify.add_argument("--regions", choices=("us", "cn"), nargs="+", required=True)
    verify.add_argument("--network", action="store_true")
    verify.add_argument("--probe-origin", default="local-static-validation")

    publish_live = subcommands.add_parser("publish-live", help="validate and publish one live playlist")
    publish_live.add_argument("--profile", choices=("us", "cn"), required=True)
    publish_live.add_argument("--input", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "candidates":
        results = refresh_candidates(root)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if any(item["status"] == "failed" for item in results) else 0
    if args.command == "compose":
        composed = compose_stable(root)
        print(json.dumps({"composed": composed}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "promote":
        promoted = promote_source(root, args.source, tuple(args.regions))
        print(json.dumps({"promoted": promoted}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "publish-live":
        destination = root / "vendor" / "live" / f"auto-{args.profile}.m3u"
        health_path = root / "health" / f"live-{args.profile}.json"
        try:
            report = publish_playlist(args.input.read_bytes(), destination, args.profile, health_path)
        except PlaylistError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0
    statuses = verify_regions(
        root,
        tuple(args.regions),
        network=args.network,
        probe_origin=args.probe_origin,
    )
    print(json.dumps(statuses, ensure_ascii=False, indent=2))
    return 1 if "error" in statuses.values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
