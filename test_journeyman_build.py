import pytest

from journeyman_build import (
    DECADES, batting_rates, pitching_rates, innings, is_pitcher, infer_pos,
    primary_team, tag_decades, assemble_batter, assemble_pitcher, classify,
)

THRESHOLDS = {
    "answer_bat_games": 1000, "answer_bat_pa": 3200,
    "answer_pit_ip": 1250, "answer_pit_games": 550,
    "guess_bat_games": 400, "guess_pit_ip": 300, "guess_pit_games": 200,
}


def outfielder(games=140):
    return {"g_all": games, "g_of": games, "g_lf": games}


# ---------------------------------------------------------------- rate stats

def test_batting_rates_match_the_official_definitions():
    # Ted Williams, 1957: 420 AB, 163 H, 28 2B, 1 3B, 38 HR, 119 BB, 5 HBP, 2 SF
    avg, obp, slg = batting_rates({
        "ab": 420, "h": 163, "x2b": 28, "x3b": 1, "hr": 38,
        "bb": 119, "hbp": 5, "sf": 2,
    })
    assert round(avg, 3) == 0.388
    assert round(obp, 3) == 0.526
    assert round(slg, 3) == 0.731


def test_batting_rates_treat_missing_era_columns_as_zero():
    """Sacrifice flies were not recorded before 1954, so Lahman leaves the column
    null. On-base percentage still has to come out right."""
    _, obp, _ = batting_rates({"ab": 100, "h": 30, "bb": 10, "hbp": None, "sf": float("nan")})
    assert round(obp, 3) == 0.364  # 40 / 110


def test_pitching_rates_recompute_from_counting_stats():
    # Bob Gibson, 1968: 304.2 IP (914 outs), 38 ER, 198 H, 62 BB
    ip, era, whip = pitching_rates({"ipouts": 914, "er": 38, "h": 198, "bb": 62})
    assert round(era, 2) == 1.12
    assert round(whip, 2) == 0.85
    assert round(ip, 1) == 304.7  # true decimal innings, used only for the rates


def test_innings_uses_thirds_not_decimals():
    assert innings(914) == 304.2   # 304 and two thirds
    assert innings(199) == 66.1    # 66 and one third
    assert innings(600) == 200.0


# ---------------------------------------------------------------- positions

def test_is_pitcher_on_the_majority_of_appearances():
    assert is_pitcher({"g_all": 100, "g_p": 60})
    assert not is_pitcher({"g_all": 100, "g_p": 12})
    assert not is_pitcher({"g_all": 0, "g_p": 0})


def test_infer_pos_splits_pitchers_by_role():
    starter = {"g_all": 40, "g_p": 40}
    assert infer_pos(starter, games_started=34, games_pitched=40) == "STARTER"
    assert infer_pos(starter, games_started=2, games_pitched=68) == "RELIEVER"


def test_infer_pos_picks_the_position_played_most():
    assert infer_pos({"g_all": 150, "g_c": 130, "g_1b": 12}) == "CATCHER"
    assert infer_pos({"g_all": 150, "g_ss": 90, "g_2b": 40, "g_of": 10}) == "INFIELD"
    assert infer_pos({"g_all": 150, "g_of": 140, "g_cf": 140}) == "OUTFIELD"
    assert infer_pos({"g_all": 150, "g_dh": 140, "g_1b": 8}) == "DH"


def test_infer_pos_falls_back_to_dh_with_no_fielding():
    assert infer_pos({"g_all": 20}) == "DH"


# ---------------------------------------------------------------- assembly

def test_primary_team_picks_most_games():
    assert primary_team([("SEA", 40), ("NYY", 95)]) == "NYY"


def test_primary_team_aggregates_duplicates():
    assert primary_team([("STL", 10), ("STL", 80), ("CHC", 60)]) == "STL"


def test_tag_decades_needs_three_seasons():
    seasons = [{"y": y} for y in (1991, 1992, 1993, 1998)] + [{"y": 2001}, {"y": 2002}]
    # 90s has 4 seasons (>=3) -> tagged; 2000s has 2 (<3) -> not tagged
    assert tag_decades(seasons) == [1990]


def test_tag_decades_multiple():
    seasons = [{"y": y} for y in (1987, 1988, 1989, 1990, 1991, 1992)]
    assert tag_decades(seasons) == [1980, 1990]


def test_tag_decades_ignores_a_decade_a_career_only_clipped():
    # three in the 90s, two on either side of it — only the 90s qualifies
    seasons = [{"y": y} for y in (1988, 1989, 1990, 1991, 1992, 2000, 2001)]
    assert tag_decades(seasons) == [1990]


def test_tag_decades_only_returns_known_decades():
    assert tag_decades([{"y": y} for y in (1921, 1922, 1923)]) == []
    assert all(d in DECADES for d in tag_decades([{"y": y} for y in (2011, 2012, 2013)]))


def test_assemble_batter_shape():
    totals = {
        1991: {"teams": [("SEA", 154)], "g": 154, "ab": 548, "h": 179, "x2b": 42,
               "x3b": 1, "hr": 22, "rbi": 100, "r": 76, "sb": 18, "bb": 71,
               "hbp": 2, "sf": 5},
        1992: {"teams": [("SEA", 142)], "g": 142, "ab": 565, "h": 174, "x2b": 39,
               "x3b": 4, "hr": 27, "rbi": 103, "r": 83, "sb": 10, "bb": 63,
               "hbp": 3, "sf": 8},
    }
    p = assemble_batter("Ken Griffey", totals, outfielder())
    assert p["name"] == "Ken Griffey" and p["type"] == "bat"
    assert p["pos"] == "OUTFIELD"
    assert p["first"] == 1991 and p["last"] == 1992
    assert p["teams"] == ["SEA"]
    assert p["games"] == 296 and p["hits"] == 353 and p["hr"] == 49
    assert p["seasons"][0]["avg"] == 0.327
    assert set(p["seasons"][0]) == {"y", "team", "g", "avg", "hr", "rbi", "r", "sb", "ops"}


def test_assemble_batter_collapses_a_traded_season_to_one_row():
    """Two stints in one year become a single season line, attributed to whoever
    the player appeared for most, with both clubs remembered for the shared-club
    clue chip. The rates must come from the combined counting stats, not from
    averaging the two stints."""
    totals = {
        1997: {"teams": [("OAK", 40), ("STL", 51)], "g": 91, "ab": 300, "h": 90,
               "x2b": 15, "x3b": 0, "hr": 31, "rbi": 70, "r": 60, "sb": 2,
               "bb": 50, "hbp": 4, "sf": 2},
    }
    p = assemble_batter("Mark McGwire", totals, {"g_all": 91, "g_1b": 91})
    assert len(p["seasons"]) == 1
    assert p["seasons"][0]["team"] == "STL"      # more games there
    assert p["teams"] == ["OAK", "STL"]           # but both are club history
    assert p["seasons"][0]["avg"] == 0.300        # 90/300, not a mean of two stints


def test_assemble_pitcher_shape():
    totals = {
        1999: {"teams": [("BOS", 31)], "g": 31, "gs": 29, "w": 23, "l": 4,
               "sv": 0, "ipouts": 640, "h": 160, "er": 49, "bb": 37, "so": 313},
    }
    p = assemble_pitcher("Pedro Martinez", totals, {"g_all": 31, "g_p": 31})
    assert p["type"] == "pit" and p["pos"] == "STARTER"
    assert p["wins"] == 23 and p["so"] == 313
    assert p["seasons"][0]["ip"] == 213.1         # 640 outs = 213 and a third
    assert p["seasons"][0]["era"] == 2.07
    assert set(p["seasons"][0]) == {"y", "team", "g", "w", "l", "era", "ip", "so", "whip"}


# ---------------------------------------------------------------- thresholds

def _bat(name, games, pa):
    return {"name": name, "type": "bat", "games": games, "pa": pa, "seasons": [{"y": 2000}]}


def _pit(name, games, ip):
    return {"name": name, "type": "pit", "games": games, "ip": ip, "seasons": [{"y": 2000}]}


def test_classify_answerable_batter_needs_games_and_plate_appearances():
    kept = classify([
        _bat("regular", 1400, 5200),
        _bat("defensive sub", 1400, 2000),   # the games without the at-bats
    ], THRESHOLDS)
    by_name = {p["name"]: p for p in kept}
    assert by_name["regular"]["answer"] is True
    assert by_name["defensive sub"]["answer"] is False


def test_classify_answerable_pitcher_on_innings_or_outings():
    kept = classify([
        _pit("ace", 500, 3000),        # innings, not enough outings
        _pit("closer", 900, 900),      # outings, not enough innings
        _pit("swingman", 300, 700),    # neither
    ], THRESHOLDS)
    by_name = {p["name"]: p for p in kept}
    assert by_name["ace"]["answer"] is True
    assert by_name["closer"]["answer"] is True
    assert by_name["swingman"]["answer"] is False


def test_classify_drops_players_under_the_guess_bar():
    kept = classify([_bat("cup of coffee", 30, 60), _pit("september callup", 8, 20)],
                    THRESHOLDS)
    assert kept == []


def test_classify_trims_seasons_from_guess_only_players():
    kept = classify([_bat("fringe regular", 600, 1800)], THRESHOLDS)
    assert kept[0]["answer"] is False
    assert "seasons" not in kept[0]


def test_classify_does_not_mutate_its_input():
    p = _bat("someone", 1400, 5200)
    classify([p], THRESHOLDS)
    assert "answer" not in p and "seasons" in p
