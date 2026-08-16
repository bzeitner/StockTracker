# StockTracker

Daily session snapshot across six futures tickers (ES, NQ, YM, RTY, GC,
and Nikkei 225/Yen NIY): overnight high/low, prior-day high/low (RTH and
full session), 15/30-minute opening-range breakout levels, and volume,
rendered on 2-minute and 5-minute charts. Built for
[IdeaFlow idea #6](https://ideaflow.bitesoftheweek.com/6/).

## Status: Phase 1 (data collection + rendering, yfinance prototype)

This is the first of a 3-phase plan (see IdeaFlow idea #6, research entry
#5 for the full writeup):

- **Phase 1 (this commit):** `daily_chart.py` pulls 1-minute bars via
  yfinance for the six configured tickers (`config.SYMBOLS` -- ES, NQ, YM,
  RTY, GC, and non-US NIY), resamples to 2m/5m, computes the levels below,
  renders a PNG per symbol/interval, and appends a stats row to
  `archive/sessions.csv`. `download_bars.py` separately backfills the last
  7 days of 1-minute bars per ticker into `archive/<TICKER>/`.
- **Phase 2 (not started):** swap the data layer to IBKR TWS or Databento
  (`GLBX.MDP3`) behind `fetch_bars()`, add explicit front-month contract
  resolution, handle DST via `zoneinfo`, add a market-calendar check for
  holidays/half-days.
- **Phase 3 (not started):** `launchd`/cron automation at the configured
  snapshot time, Discord/Slack/email delivery, run against both ES and NQ.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python daily_chart.py --date 2026-08-14 --symbol ES
python download_bars.py               # backfill last 7 days, all 6 tickers
```

`daily_chart.py` output lands in `archive/<date>/`:
- `<SYMBOL>_1m.csv` — raw 1-minute bars for the session
- `charts/<SYMBOL>_2min.png`, `charts/<SYMBOL>_5min.png` — rendered charts
- `archive/sessions.csv` — one row per symbol/session with every computed level

`download_bars.py` output lands in `archive/<TICKER>/`:
- `<TICKER>_1m_<fetched-date>.csv` — last 7 days of 1-minute bars, one
  folder per ticker (ES, NQ, YM, RTY, GC, NIY)

`archive/` is gitignored; both scripts write local-only output.

## Level definitions

Locked in `config.py`, per idea #6 research entry #5 §2 (multiple
defensible definitions exist for each of these; picking wrong makes the
chart quietly disagree with your trading platform):

| Level | Definition used |
|---|---|
| Overnight high/low (ONH/ONL) | 6:00 PM ET prior day → 9:30 AM ET cash open |
| Yesterday high/low | Both RTH-only and full 23h Globex session, plotted separately |
| ORB 15 / 30 | From the 9:30 ET cash open, wicks included |
| Volume | Front-month contract only |

## Known limitations (Phase 1, by design)

- **yfinance 1-minute history is capped at 7 calendar days.** Fine for
  prototyping and for a same-day/prior-day snapshot; not sufficient to
  backfill a long archive. Phase 2 swaps this out.
- **Contract roll handling is opaque.** yfinance's continuous tickers
  (`ES=F`, `NQ=F`, etc.) blend contracts; around quarterly roll dates the
  levels can be off by tens of points. Phase 2 adds explicit front-month
  resolution.
- **Futures volume from yfinance is not reliably front-month contract
  volume.** Treat volume figures as directional only until Phase 2.
- **Timezone handling** currently assumes bars come back tz-aware in a
  form `tz_convert("America/New_York")` accepts; this has not yet been
  stress-tested across a DST transition.
- **Session-hours definitions (overnight/cash-open/ORB) are US-hours.**
  They're literally correct for ES/NQ/YM/RTY; for GC and NIY (non-US-hours
  products), treat those levels as directional until each product's own
  session is modeled.

## Validation

Per idea #6's own next step: before trusting this output, compare a
rendered chart against a TradingView chart with an equivalent
ORB/prior-day-levels Pine script loaded (e.g. "Previous Day, Pre Market
and ORB Levels" by nicholaslimwc) for the same session and confirm the
levels agree. Not yet done as of this commit — see IdeaFlow idea #6 for
the open item.

## Tests

```bash
pip install pytest
python -m pytest tests/
```
