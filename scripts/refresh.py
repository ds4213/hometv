from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from hometv.refresh import promote_source, refresh_candidates, verify_regions


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Manage HomeTV FongMi configurations")
    command.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    subcommands = command.add_subparsers(dest="command", required=True)
    subcommands.add_parser("candidates", help="refresh enabled candidate sources")

    promote = subcommands.add_parser("promote", help="promote a verified candidate")
    promote.add_argument("--source", required=True)
    promote.add_argument("--regions", choices=("us", "cn"), nargs="+", required=True)

    verify = subcommands.add_parser("verify", help="validate stable configurations")
    verify.add_argument("--regions", choices=("us", "cn"), nargs="+", required=True)
    verify.add_argument("--network", action="store_true")
    verify.add_argument("--probe-origin", default="local-static-validation")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "candidates":
        results = refresh_candidates(root)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if any(item["status"] == "failed" for item in results) else 0
    if args.command == "promote":
        promoted = promote_source(root, args.source, tuple(args.regions))
        print(json.dumps({"promoted": promoted}, ensure_ascii=False, indent=2))
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
