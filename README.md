# ⚾ Journeyman — MLB

Guess the mystery major leaguer from their career — revealed one season at a
time. A daily puzzle for baseball nerds, with a twist: play the **All-Time**
game, or pick a single **decade** and test how well you know the 50s through
the 2020s.

Sister games: **[Journeyman — NBA](https://nba-journeyman.netlify.app)**,
**[Journeyman — AFL](https://footy-journeyman.netlify.app)** and
**[Globetrotter](https://country-globetrotter.netlify.app)** — all reachable
from the *Play our other games* button at the top of the page.

## How to play

A mystery player's career record appears one season at a time, in a random
order. Baseball careers come in two shapes and no single stat line reads
sensibly for both, so the table swaps its columns to match the player:

- **Hitters** — club, games, batting average, home runs, RBI, runs, stolen
  bases and OPS.
- **Pitchers** — club, games, wins, losses, ERA, innings, strikeouts and WHIP.

Rules:

- Every wrong guess reveals **another season**. The fewer seasons you need, the
  better your score.
- After each miss you get **clue chips**: whether you shared a club, whether you
  played the same position, and whether the answer debuted earlier or later than
  your guess.
- **Normal:** 8 guesses. **Hard mode:** 5 guesses, clubs hidden, no clue chips.

Come back every day for a fresh puzzle, share your result grid, and chase your
streak — each game mode tracks its own, and a missed day resets it. One go per
puzzle per day: your progress is saved as you play, so closing the tab mid-game
picks up where you left off rather than dealing a new player.

## Game modes

- **All-Time** — one daily player from 1950 to the present.
- **Decades** — a separate daily puzzle for the 50s / 60s / 70s / 80s / 90s /
  2000s / 2010s / 2020s. Players who spanned eras show up in more than one.
- **Practice** — unlimited random players whenever you want more.

## Who makes the cut

The pool is deliberately restricted to careers with some substance behind them,
pitched at the same level as the sister games (roughly five-plus seasons of
first-team duty to be an answer, a couple of seasons to be a guess). Because a
hitter, a starter and a closer accumulate completely different counting stats,
each is measured in its own currency — see `THRESHOLDS` in `build_players.py`:

| | Can be the answer | Appears in autocomplete |
|---|---|---|
| Hitters | 1,000 games **and** 3,200 plate appearances | 400 games |
| Pitchers | 1,250 innings **or** 550 appearances | 300 innings **or** 200 appearances |

The plate-appearance bar keeps a long-serving defensive substitute from turning
up as the mystery player, and the appearances bar for pitchers means a career
reliever is not held to a starter's innings.

## Building the data

`players.json` is generated from the
[Lahman Baseball Database](https://sabr.org/lahman-database/), the long-running
public compilation of complete MLB batting, pitching and fielding records. The
tables are pulled from the CRAN `Lahman` package's repository, which republishes
them each off-season with the year just gone.

```sh
pip install -r requirements.txt
python build_players.py players.json   # writes players.json
python make_fallback.py                # refreshes the offline set in index.html
pytest -q                              # data contract + build helper tests
```

`.github/workflows/refresh-data.yml` does the same thing monthly and commits the
result if anything changed.

## Running it locally

The page fetches `players.json` at runtime, so it needs a server rather than a
`file://` open:

```sh
python3 -m http.server 8000    # then visit http://localhost:8000
```

Opened without one, it falls back to the pool embedded in `index.html` and still
plays.

## Deploying

Static site, no build step — `vercel.json` sets the cache headers and nothing
else. Import the repository in Vercel and accept the defaults (framework preset
*Other*, no build command, root directory `.`).

## Configuration

Three constants at the top of the `<script>` block in `index.html`:

- `COFFEE_URL` — Buy Me a Coffee link behind the ☕ button.
- `SITE_URL` — canonical URL used in the shared result. Empty means "use
  whatever address the page is being served from".
- `GA_ID` — Google Analytics measurement ID. Empty means no analytics tag is
  loaded at all; set it to `G-XXXXXXXXXX` and the snippet injects itself.

## Credits

Player statistics from the [Lahman Baseball Database](https://sabr.org/lahman-database/).
Not affiliated with MLB or any club — no logos, player photos, or league marks
are used, just public career stats. Built by
[Nadav Moskow](https://buymeacoffee.com/nadavmoskow); if you enjoy it, the ☕
button keeps it running.
