#!/usr/bin/env python3
"""Refresh the offline FALLBACK set embedded in index.html.

The game fetches players.json at runtime, which fails when the page is opened
straight off the filesystem or from a sandbox with no network. Rather than show
an empty table, index.html carries a small hand-sized pool inline. This script
regenerates it from the freshly built players.json so the two never drift.

Run after build_players.py:  python3 make_fallback.py
"""
import json, re, sys
from collections import defaultdict

from journeyman_build import DECADES

PLAYERS = sys.argv[1] if len(sys.argv) > 1 else "players.json"
PAGE = sys.argv[2] if len(sys.argv) > 2 else "index.html"
PER_DECADE = 8   # per decade, per kind of player — enough that every decade
                 # mode still has something to deal offline


def main():
    data = json.load(open(PLAYERS))
    answers = [p for p in data if p.get("answer") and p.get("seasons")]

    # the longest careers of each decade, batters and pitchers kept separate so
    # the offline set can still serve up either kind of table
    buckets = defaultdict(list)
    for p in sorted(answers, key=lambda p: -p["games"]):
        for d in p["decades"]:
            buckets[(d, p["type"])].append(p)

    picked, seen = [], set()
    for d in DECADES:
        for kind in ("bat", "pit"):
            for p in buckets[(d, kind)][:PER_DECADE]:
                if p["name"] not in seen:
                    seen.add(p["name"])
                    picked.append(p)
    picked.sort(key=lambda p: -p["games"])

    blob = json.dumps(picked, separators=(",", ":"))
    page = open(PAGE).read()
    new, n = re.subn(r"^const FALLBACK = .*;$", "const FALLBACK = " + blob + ";",
                     page, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("could not find the `const FALLBACK = ...;` line in " + PAGE)
    open(PAGE, "w").write(new)
    print(f"embedded {len(picked)} players ({len(blob) // 1024} KB) into {PAGE}")


if __name__ == "__main__":
    main()
