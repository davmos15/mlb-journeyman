"""Journeyman — MLB: pure, network-free build helpers.

Shared by build_players.py (which supplies data from the Lahman database) and
the tests. Baseball splits cleanly into two kinds of career, so a player is
built as either a BATTER or a PITCHER and carries the stat line that suits
them — there is no single row that reads sensibly for both.

Position is derived from where a player actually appeared (Lahman's
Appearances table), bucketed coarsely so the "same position" clue chip stays a
clue rather than a giveaway.
"""

DECADES = [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]

# Coarse position buckets. Pitchers split by role because a closer and an ace
# are different animals; fielders collapse to the three shapes a fan thinks in.
POSITIONS = ["STARTER", "RELIEVER", "CATCHER", "INFIELD", "OUTFIELD", "DH"]


def _f(v):
    """Lahman leaves whole columns null for early seasons (sacrifice flies did
    not exist as a stat until 1954, hit-by-pitch is patchy). Missing means the
    event was not recorded, and treating it as zero is the standard fix."""
    try:
        if v is None or v != v:  # NaN
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _r(v, n):
    return round(v, n)


def _div(a, b):
    return a / b if b else 0.0


# ---------------------------------------------------------------------------
# rate stats — always recomputed from summed counting stats, never averaged
# ---------------------------------------------------------------------------

def batting_rates(t):
    """t: dict of summed counting stats for one season (or a career).
    Returns (avg, obp, slg). Uses the official definitions, with the caveat in
    _f above for eras that did not record SF/HBP."""
    ab, h, bb, hbp, sf = _f(t.get("ab")), _f(t.get("h")), _f(t.get("bb")), _f(t.get("hbp")), _f(t.get("sf"))
    d2, d3, hr = _f(t.get("x2b")), _f(t.get("x3b")), _f(t.get("hr"))
    singles = h - d2 - d3 - hr
    tb = singles + 2 * d2 + 3 * d3 + 4 * hr
    avg = _div(h, ab)
    obp = _div(h + bb + hbp, ab + bb + hbp + sf)
    slg = _div(tb, ab)
    return avg, obp, slg


def innings(ipouts):
    """Outs recorded -> innings pitched in the notation the sport actually uses:
    the digit after the point is a count of thirds, so 199 outs is 66.1 (sixty-six
    and one third), not 66.3. Never add two of these together — go back to outs.
    (classify() compares a career figure against a four-digit innings bar, where
    being under an inning out is immaterial.)"""
    o = int(round(_f(ipouts)))
    return float(f"{o // 3}.{o % 3}")


def pitching_rates(t):
    """t: dict of summed counting stats. Returns (ip, era, whip), where ip is the
    true decimal innings figure the rates divide by — see innings() for the value
    that gets shown. ERA and WHIP are recomputed rather than taken from Lahman's
    own columns so a traded season's two stints combine correctly."""
    ip = _div(_f(t.get("ipouts")), 3.0)
    era = _div(_f(t.get("er")) * 9.0, ip)
    whip = _div(_f(t.get("h")) + _f(t.get("bb")), ip)
    return ip, era, whip


# ---------------------------------------------------------------------------
# position / role
# ---------------------------------------------------------------------------

def is_pitcher(app):
    """app: dict of career games by position from Appearances.
    A pitcher is someone who mostly pitched. The majority test keeps two-way
    players (and the pitcher who spent a year in the outfield) on the side
    where the bulk of their career actually happened."""
    total = _f(app.get("g_all"))
    return total > 0 and _div(_f(app.get("g_p")), total) >= 0.5


def infer_pos(app, games_started=0, games_pitched=0):
    """Coarse bucket from career appearances. Pitchers split STARTER/RELIEVER on
    whether at least half their outings were starts; fielders go to whichever of
    catcher / infield / outfield they played most, with DH as the fallback for
    careers spent almost entirely in the batter's box."""
    if is_pitcher(app):
        return "STARTER" if _div(_f(games_started), _f(games_pitched)) >= 0.5 else "RELIEVER"
    catcher = _f(app.get("g_c"))
    infield = sum(_f(app.get(k)) for k in ("g_1b", "g_2b", "g_3b", "g_ss"))
    outfield = _f(app.get("g_of")) or sum(_f(app.get(k)) for k in ("g_lf", "g_cf", "g_rf"))
    dh = _f(app.get("g_dh"))
    best = max(
        ("CATCHER", catcher), ("INFIELD", infield), ("OUTFIELD", outfield), ("DH", dh),
        key=lambda kv: kv[1],
    )
    return best[0] if best[1] > 0 else "DH"


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def primary_team(rows):
    """rows: iterable of (team, games). Returns the team with the most games,
    aggregating duplicates. Collapses a mid-season trade to one team."""
    agg = {}
    for team, g in rows:
        agg[team] = agg.get(team, 0) + g
    best, bestg = None, -1
    for team, g in agg.items():
        if g > bestg:
            best, bestg = team, g
    return best


def tag_decades(seasons, min_seasons=3):
    """A decade qualifies if the player has >= min_seasons seasons in it (the
    same 'more than 2 seasons' rule the sister games use). Baseball seasons sit
    inside a single calendar year, so no end-year fudge is needed."""
    counts = {}
    for s in seasons:
        d = (s["y"] // 10) * 10
        counts[d] = counts.get(d, 0) + 1
    return sorted(d for d in DECADES if counts.get(d, 0) >= min_seasons)


def assemble_batter(name, season_totals, app):
    """season_totals: {year: {"teams":[(team,g)...], counting stats summed}}.
    Returns a player dict WITHOUT the `answer` flag (added later by classify)."""
    seasons, teams = [], []
    car = {}
    for y in sorted(season_totals):
        t = season_totals[y]
        team = primary_team(t["teams"])
        for tm, _g in t["teams"]:
            if tm not in teams:
                teams.append(tm)
        avg, obp, slg = batting_rates(t)
        seasons.append({
            "y": y, "team": team, "g": int(_f(t.get("g"))),
            "avg": _r(avg, 3), "hr": int(_f(t.get("hr"))), "rbi": int(_f(t.get("rbi"))),
            "r": int(_f(t.get("r"))), "sb": int(_f(t.get("sb"))), "ops": _r(obp + slg, 3),
        })
        for k in ("g", "ab", "h", "x2b", "x3b", "hr", "rbi", "r", "sb", "bb", "hbp", "sf"):
            car[k] = car.get(k, 0.0) + _f(t.get(k))
    return {
        "name": name, "type": "bat", "pos": infer_pos(app),
        "first": seasons[0]["y"], "last": seasons[-1]["y"], "teams": teams,
        "games": int(car.get("g", 0)), "pa": int(car.get("ab", 0) + car.get("bb", 0)
                                                 + car.get("hbp", 0) + car.get("sf", 0)),
        "hits": int(car.get("h", 0)), "hr": int(car.get("hr", 0)),
        "decades": tag_decades(seasons), "seasons": seasons,
    }


def assemble_pitcher(name, season_totals, app):
    """As assemble_batter, but for the pitching line."""
    seasons, teams = [], []
    car = {}
    for y in sorted(season_totals):
        t = season_totals[y]
        team = primary_team(t["teams"])
        for tm, _g in t["teams"]:
            if tm not in teams:
                teams.append(tm)
        ip, era, whip = pitching_rates(t)
        seasons.append({
            "y": y, "team": team, "g": int(_f(t.get("g"))),
            "w": int(_f(t.get("w"))), "l": int(_f(t.get("l"))),
            "era": _r(era, 2), "ip": innings(t.get("ipouts")), "so": int(_f(t.get("so"))),
            "whip": _r(whip, 2),
        })
        for k in ("g", "gs", "w", "l", "so", "ipouts", "er", "h", "bb", "sv"):
            car[k] = car.get(k, 0.0) + _f(t.get(k))
    return {
        "name": name, "type": "pit",
        "pos": infer_pos(app, car.get("gs", 0), car.get("g", 0)),
        "first": seasons[0]["y"], "last": seasons[-1]["y"], "teams": teams,
        "games": int(car.get("g", 0)), "ip": innings(car.get("ipouts", 0)),
        "wins": int(car.get("w", 0)), "so": int(car.get("so", 0)),
        "decades": tag_decades(seasons), "seasons": seasons,
    }


# ---------------------------------------------------------------------------
# thresholds
# ---------------------------------------------------------------------------

def classify(players, t):
    """Set the `answer` flag, drop players below the guess threshold, and trim
    `seasons` from guess-only players. Returns the kept players.

    `t` is a thresholds dict (see build_players.py). The bars are set in the
    currency each kind of career is actually measured in — plate appearances for
    a hitter, innings for a starter, outings for a reliever — so that a bench
    bat who racked up games as a defensive replacement does not become the
    mystery player, and a closer is not held to a starter's innings.
    """
    out = []
    for p in players:
        if p["type"] == "bat":
            answerable = p["games"] >= t["answer_bat_games"] and p["pa"] >= t["answer_bat_pa"]
            guessable = p["games"] >= t["guess_bat_games"]
        else:
            answerable = p["ip"] >= t["answer_pit_ip"] or p["games"] >= t["answer_pit_games"]
            guessable = p["ip"] >= t["guess_pit_ip"] or p["games"] >= t["guess_pit_games"]
        if not (answerable or guessable):
            continue
        p = dict(p)
        p["answer"] = answerable
        if not answerable:
            p.pop("seasons", None)
        out.append(p)
    return out
