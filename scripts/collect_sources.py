"""Collect pinned upstream source without installing or executing it.

Usage: python3 scripts/collect_sources.py [--download]
The default only prints the collection plan. Requires git and network access.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    sources = json.loads((ROOT / "upstreams.lock.json").read_text())["sources"]
    for source in sources:
        if not re.fullmatch(r"[a-z0-9_]+", source["id"]):
            raise ValueError("unsafe destination")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", source["repository"]):
            raise ValueError("unsupported repository URL")
        if not re.fullmatch(r"[a-f0-9]{40}", source["revision"]):
            raise ValueError("pin a full commit SHA")
    for source in sources:
        target = ROOT / "out" / "upstreams" / source["id"]
        print(f'{source["id"]}: {source["revision"]} ({source["license"]})')
        if not args.download:
            continue
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing checkout: {target}")
        target.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "fetch", "--depth=1", "--no-tags",
                        source["repository"], source["revision"]], check=True, timeout=120)
        fetched = subprocess.check_output(["git", "-C", str(target), "rev-parse", "FETCH_HEAD"], text=True).strip()
        if fetched != source["revision"]:
            raise ValueError("downloaded revision mismatch")
        subprocess.run(["git", "-C", str(target), "-c", "core.hooksPath=/dev/null",
                        "checkout", "--detach", fetched], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
