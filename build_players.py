#!/usr/bin/env python3
"""Journeyman — MLB dataset builder.

Builds the season-aggregated players.json the game consumes from the Lahman
Baseball Database, the long-running public compilation of complete MLB batting,
pitching and fielding records. The tables are pulled from the CRAN `Lahman`
package's GitHub repository, which publishes them as R data files and is
refreshed each off-season with the year just gone.

Baseball careers come in two shapes, and one stat line cannot serve both: a
pitcher's season is wins, ERA, innings and strikeouts, a hitter's is average,
home runs, runs batted in and OPS. Every player is therefore built as one or
the other — whichever side of the ball the bulk of their appearances sat on —
and the game swaps its table columns to match the mystery player.

Run:  python3 build_players.py players.json
      python3 build_players.py players.json --cache-dir /tmp/lahman
"""
import sys, os, json, io, urllib.request
from collections import defaultdict

import pyreadr

from journeyman_build import (
    assemble_batter, assemble_pitcher, classify, is_pitcher, DECADES,
)

# Tunables -------------------------------------------------------------
START_YEAR = 1950   # first season included; earlier careers are truncated, so
                    # the cutoff is also the point the footer advertises

# Answer/guess bars, chosen to land where the sister games sit: answerable is
# roughly five-plus seasons of genuine first-team duty, guessable is a couple of
# seasons in the majors. Each kind of career is measured in its own currency —
# see classify() in journeyman_build.py.
THRESHOLDS = {
    "answer_bat_games": 1000,   # ~6.5 seasons as a regular
    "answer_bat_pa":    3200,   # and enough at-bats that they actually played
    "answer_pit_ip":    1250,   # ~6 seasons in a rotation
    "answer_pit_games":  550,   # or a long career out of the bullpen
    "guess_bat_games":   400,
    "guess_pit_ip":      300,
    "guess_pit_games":   200,
}

LAHMAN_BASE = "https://raw.githubusercontent.com/cdalzell/Lahman/master/data"
TABLES = ["Batting", "Pitching", "Appearances", "People", "Teams"]


def fetch_table(name, cache_dir):
    """Download one Lahman table (or read it from the cache) as a DataFrame."""
    path = os.path.join(cache_dir, f"{name}.RData") if cache_dir else None
    if path and os.path.exists(path):
        blob = open(path, "rb").read()
    else:
        url = f"{LAHMAN_BASE}/{name}.RData"
        print("Fetching", url, "…", flush=True)
        with urllib.request.urlopen(url, timeout=180) as r:
            blob = r.read()
        if path:
            os.makedirs(cache_dir, exist_ok=True)
            open(path, "wb").write(blob)
    if not path:
        # pyreadr only reads from disk, so an uncached fetch still needs a file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".RData", delete=False) as fh:
            fh.write(blob)
            path = fh.name
        try:
            return pyreadr.read_r(path)[name]
        finally:
            os.unlink(path)
    return pyreadr.read_r(path)[name]


def team_codes(teams_df):
    """(year, Lahman teamID) -> the Baseball-Reference abbreviation.

    Lahman's own team IDs are league-and-city codes that no fan would recognise
    (NYA, SLN, CHN); teamIDBR is the familiar NYY / STL / CHC. Franchises that
    moved or rebranded get the code they used that season, which is the point —
    a 1965 line should read MLN, not ATL."""
    out = {}
    for r in teams_df.itertuples():
        br = getattr(r, "teamIDBR", None)
        out[(int(r.yearID), str(r.teamID))] = str(br) if br and br == br else str(r.teamID)
    return out


def num(v):
    return 0.0 if v is None or v != v else float(v)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "players.json"
    cache_dir = None
    if "--cache-dir" in sys.argv:
        cache_dir = sys.argv[sys.argv.index("--cache-dir") + 1]

    t = {name: fetch_table(name, cache_dir) for name in TABLES}
    codes = team_codes(t["Teams"])

    names = {}
    for r in t["People"].itertuples():
        first = r.nameFirst if r.nameFirst == r.nameFirst and r.nameFirst else ""
        last = r.nameLast if r.nameLast == r.nameLast and r.nameLast else ""
        names[r.playerID] = (f"{first} {last}").strip() or r.playerID

    # career appearances by position, used for the pitcher test and the bucket
    app = defaultdict(lambda: defaultdict(float))
    app_cols = ["g_all", "g_p", "g_c", "g_1b", "g_2b", "g_3b", "g_ss",
                "g_lf", "g_cf", "g_rf", "g_of", "g_dh"]
    for r in t["Appearances"].itertuples():
        if int(r.yearID) < START_YEAR:
            continue
        a = app[r.playerID]
        for col in app_cols:
            a[col] += num(getattr(r, col.replace("g_all", "G_all").replace("g_", "G_"), 0))

    def collect(df, spec):
        """Aggregate a Lahman stat table into {playerID: {year: totals}}, summing
        the stints of a traded season and remembering each stint's team so the
        season can be attributed to wherever the player played most."""
        per = defaultdict(lambda: defaultdict(lambda: {"teams": []}))
        for r in df.itertuples():
            y = int(r.yearID)
            if y < START_YEAR:
                continue
            slot = per[r.playerID][y]
            code = codes.get((y, str(r.teamID)), str(r.teamID))
            slot["teams"].append((code, num(r.G)))
            for key, col in spec.items():
                slot[key] = slot.get(key, 0.0) + num(getattr(r, col))
        return per

    bat_raw = collect(t["Batting"], {
        "g": "G", "ab": "AB", "r": "R", "h": "H", "x2b": "X2B", "x3b": "X3B",
        "hr": "HR", "rbi": "RBI", "sb": "SB", "bb": "BB", "hbp": "HBP", "sf": "SF",
    })
    pit_raw = collect(t["Pitching"], {
        "g": "G", "gs": "GS", "w": "W", "l": "L", "sv": "SV", "ipouts": "IPouts",
        "h": "H", "er": "ER", "bb": "BB", "so": "SO",
    })

    players = []
    for pid, seasons in pit_raw.items():
        if is_pitcher(app[pid]):
            players.append(assemble_pitcher(names.get(pid, pid), seasons, app[pid]))
    for pid, seasons in bat_raw.items():
        if not is_pitcher(app[pid]):
            players.append(assemble_batter(names.get(pid, pid), seasons, app[pid]))

    kept = classify(players, THRESHOLDS)
    kept.sort(key=lambda p: -p["games"])

    # Disambiguate shared display names (baseball has plenty) by debut club and
    # year. Done after classify so a name is only qualified when both bearers
    # actually made the pool — otherwise Pete Rose gets a suffix on account of a
    # son who played eleven games.
    counts = {}
    for p in kept:
        counts[p["name"]] = counts.get(p["name"], 0) + 1
    for p in kept:
        if counts[p["name"]] > 1:
            p["name"] = f'{p["name"]} ({p["teams"][0]}, {p["first"]})'

    answers = [p for p in kept if p["answer"]]
    bats = sum(1 for p in answers if p["type"] == "bat")
    print(f"{len(kept)} guessable, {len(answers)} answerable "
          f"({bats} batters, {len(answers) - bats} pitchers)")

    from collections import Counter
    dc = Counter(d for p in answers for d in p["decades"])
    print("answerable per decade:", {d: dc.get(d, 0) for d in DECADES})

    json.dump(kept, open(out_path, "w"), separators=(",", ":"))
    print(f"wrote {out_path} ({os.path.getsize(out_path) // 1024} KB)")


if __name__ == "__main__":
    main()
