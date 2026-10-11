"""Generate only US VOD; never rebuild China or live artifacts."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hometv.build import build_us
from hometv.refresh import GITHUB_RAW_BASE
from hometv.us_vod import extend_us_vod
from hometv.validate import validate_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-base", default=GITHUB_RAW_BASE)
    parser.add_argument("--output", default="stable/us-preview.json")
    args = parser.parse_args()
    source = json.loads((ROOT / "candidates/nitan-dm/upstream.json").read_text(encoding="utf-8"))
    result = extend_us_vod(ROOT, build_us(source), args.delivery_base)
    errors = [f for f in validate_config(result, "us") if f.severity == "error"]
    if errors:
        raise SystemExit(str(errors))
    destination = (ROOT / args.output).resolve()
    if not destination.is_relative_to(ROOT):
        raise SystemExit("output must be inside the repository")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    print(json.dumps({"output": str(destination), "sites": len(result["sites"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
