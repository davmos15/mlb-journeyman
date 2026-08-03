"""Contract tests for the built players.json.

These guard the shape index.html relies on, and run in CI after every data
refresh so a bad rebuild never gets committed.
"""
import json, os, pytest

from journeyman_build import DECADES
from build_players import START_YEAR, THRESHOLDS

DATA = "players.json"
pytestmark = pytest.mark.skipif(not os.path.exists(DATA), reason="players.json not built")

BAT_KEYS = {"y", "team", "g", "avg", "hr", "rbi", "r", "sb", "ops"}
PIT_KEYS = {"y", "team", "g", "w", "l", "era", "ip", "so", "whip"}


def load():
    return json.load(open(DATA, encoding="utf-8"))


def test_nonempty_and_has_answers():
    players = load()
    assert len(players) > 1000
    answers = [p for p in players if p.get("answer")]
    assert len(answers) > 500


def test_every_player_is_a_batter_or_a_pitcher():
    for p in load():
        assert p["type"] in ("bat", "pit"), p["name"]


def test_answer_players_carry_a_full_season_line():
    for p in load():
        if not p.get("answer"):
            continue
        assert p.get("seasons"), p["name"]
        want = PIT_KEYS if p["type"] == "pit" else BAT_KEYS
        for s in p["seasons"]:
            assert set(s) == want, (p["name"], s["y"], set(s) ^ want)


def test_guess_only_players_are_trimmed():
    """Players who can only ever be a guess ship without their season table —
    that is most of the file, and carrying it would multiply the download."""
    for p in load():
        if not p.get("answer"):
            assert "seasons" not in p, p["name"]


def test_headline_career_fields_match_the_player_kind():
    for p in load():
        if p["type"] == "pit":
            assert {"ip", "wins", "so"} <= set(p), p["name"]
        else:
            assert {"pa", "hits", "hr"} <= set(p), p["name"]


def test_answers_clear_the_thresholds_they_were_built_with():
    for p in load():
        if not p.get("answer"):
            continue
        if p["type"] == "pit":
            assert (p["ip"] >= THRESHOLDS["answer_pit_ip"]
                    or p["games"] >= THRESHOLDS["answer_pit_games"]), p["name"]
        else:
            assert p["games"] >= THRESHOLDS["answer_bat_games"], p["name"]
            assert p["pa"] >= THRESHOLDS["answer_bat_pa"], p["name"]


def test_every_decade_has_a_pool():
    answers = [p for p in load() if p.get("answer")]
    for d in DECADES:
        pool = [p for p in answers if d in p.get("decades", [])]
        assert len(pool) >= 40, f"decade {d} only has {len(pool)} answerable players"


def test_both_kinds_of_player_are_answerable_in_every_decade():
    """The table swaps columns for a pitcher, so every decade mode needs some of
    each — otherwise a whole mode quietly becomes hitters-only."""
    answers = [p for p in load() if p.get("answer")]
    for d in DECADES:
        for kind in ("bat", "pit"):
            pool = [p for p in answers if d in p.get("decades", []) and p["type"] == kind]
            assert len(pool) >= 15, f"decade {d} has only {len(pool)} {kind} answers"


def test_names_are_unique():
    names = [p["name"] for p in load()]
    dupes = {n for n in names if names.count(n) > 1} if len(names) != len(set(names)) else set()
    assert not dupes, sorted(dupes)[:5]


def test_years_within_range():
    for p in load():
        assert START_YEAR <= p["first"] <= p["last"], p["name"]
        assert p["seasons"][0]["y"] == p["first"] if p.get("seasons") else True


def test_seasons_are_chronological_and_unique():
    for p in load():
        if not p.get("answer"):
            continue
        years = [s["y"] for s in p["seasons"]]
        assert years == sorted(years), p["name"]
        assert len(years) == len(set(years)), p["name"]


def test_rate_stats_are_sane():
    for p in load():
        if not p.get("answer"):
            continue
        for s in p["seasons"]:
            if p["type"] == "pit":
                assert 0 <= s["era"] < 200, (p["name"], s["y"])
                assert 0 <= s["whip"] < 20, (p["name"], s["y"])
                assert s["ip"] >= 0 and round(s["ip"] % 1, 1) in (0.0, 0.1, 0.2), (p["name"], s["y"])
            else:
                assert 0 <= s["avg"] <= 1, (p["name"], s["y"])
                assert 0 <= s["ops"] <= 5, (p["name"], s["y"])


def test_embedded_fallback_stays_in_step_with_the_data():
    """index.html carries an offline pool for when the players.json fetch fails.
    It is generated from this file, so it must parse and use the same shape."""
    import re
    page = open("index.html", encoding="utf-8").read()
    m = re.search(r"^const FALLBACK = (.*);$", page, re.M)
    assert m, "no FALLBACK line in index.html"
    fallback = json.loads(m.group(1))
    assert len(fallback) >= 20
    names = {p["name"] for p in load()}
    for p in fallback:
        assert p["name"] in names, f"{p['name']} is no longer in players.json"
        assert p["answer"] and p["seasons"]
