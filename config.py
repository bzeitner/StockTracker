"""
Level and timing configuration for the daily ES/NQ session chart.

Per idea #6 research (entry #5): resolve every ambiguous level definition
here, in one place, before any stats get written to the archive. Redefining
levels later invalidates every archived row that used the old definition.
"""
from zoneinfo import ZoneInfo

# --- Symbols -----------------------------------------------------------
# yfinance continuous futures tickers. Phase 1 only; swap for an explicit
# front-month contract resolver (IBKR/Databento) before trusting the
# archive long-term -- see README "Known limitations".
SYMBOLS = {
    "ES": "ES=F",
    "NQ": "NQ=F",
}

# --- Timeframes to render ------------------------------------------------
RENDER_INTERVALS = ["2min", "5min"]

# --- Timezones -----------------------------------------------------------
TZ_ET = ZoneInfo("America/New_York")
TZ_PT = ZoneInfo("America/Los_Angeles")

# --- Snapshot trigger time (config, not hardcoded; see entry #5 §1) ------
SNAPSHOT_TIME_PT = "10:00"

# --- Session definitions ---------------------------------------------------
# Overnight (Globex) session: prior day 6:00 PM ET -> today 9:30 AM ET.
OVERNIGHT_START_ET = "18:00"
CASH_OPEN_ET = "09:30"

# Opening range breakout windows, measured from the 9:30 ET cash open.
ORB_WINDOWS_MIN = [15, 30]

# Yesterday high/low: compute both and plot both, styled differently
# (see entry #5 §2 -- RTH-only vs full 23h Globex session disagree and
# that disagreement is itself informative).
YESTERDAY_RTH_ONLY = True
YESTERDAY_FULL_SESSION = True

# --- Output paths ----------------------------------------------------------
ARCHIVE_DIR = "archive"
CHARTS_SUBDIR = "charts"
STATS_FILE = "sessions.csv"
