#!/usr/bin/env python3
"""
Phase 1 (idea #6, entry #5's plan): pull recent 1-minute ES/NQ bars via
yfinance, resample to 2m/5m, compute the key session levels, render a PNG
chart per symbol/interval, and append a stats row to the archive.

Usage:
    python daily_chart.py                 # today, both symbols, both intervals
    python daily_chart.py --date 2026-08-14
    python daily_chart.py --symbol ES

This is intentionally a plain script, not a service: it is meant to be run
manually or from cron/launchd once it has been validated against a
TradingView reference chart (see README). No AI, no framework -- per the
idea's own next-action note ("if data load does not require AI, all the
better - it can be done as a shell script on the server").
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path

import mplfinance as mpf
import pandas as pd
import yfinance as yf

import config


def fetch_1m_bars(ticker: str, lookback_days: int = 5) -> pd.DataFrame:
    """Pull 1-minute bars for the last `lookback_days` days.

    yfinance caps 1-minute history at 7 calendar days (entry #5), so this
    is a hard ceiling, not a tunable knob past that point.
    """
    lookback_days = min(lookback_days, 7)
    data = yf.download(
        ticker,
        period=f"{lookback_days}d",
        interval="1m",
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        raise RuntimeError(f"yfinance returned no 1m bars for {ticker}")
    # yfinance can return a MultiIndex column set for a single ticker.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.index = data.index.tz_convert(config.TZ_ET)
    return data


def resample(bars_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    out = bars_1m.resample(rule).agg(agg).dropna(subset=["Open"])
    return out


def session_date_index(bars_1m: pd.DataFrame, session_date: dt.date) -> pd.DatetimeIndex:
    """Rows belonging to the Globex session that closes on `session_date`:
    prior calendar day 18:00 ET through `session_date` 17:00 ET.
    """
    start = dt.datetime.combine(
        session_date - dt.timedelta(days=1),
        dt.time.fromisoformat(config.OVERNIGHT_START_ET),
        tzinfo=config.TZ_ET,
    )
    end = dt.datetime.combine(session_date, dt.time(17, 0), tzinfo=config.TZ_ET)
    return bars_1m.loc[(bars_1m.index >= start) & (bars_1m.index < end)].index


def _window(bars: pd.DataFrame, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    return bars.loc[(bars.index >= start) & (bars.index < end)]


def compute_levels(bars_1m: pd.DataFrame, session_date: dt.date) -> dict:
    """Compute ONH/ONL, PDH/PDL (RTH + full session), and ORB15/30 for
    `session_date`, per the definitions locked in config.py / entry #5 §2.
    """
    idx = session_date_index(bars_1m, session_date)
    session = bars_1m.loc[idx]
    if session.empty:
        raise RuntimeError(f"No bars found for session date {session_date}")

    cash_open = dt.datetime.combine(
        session_date, dt.time.fromisoformat(config.CASH_OPEN_ET), tzinfo=config.TZ_ET
    )
    overnight_end = cash_open
    overnight = session.loc[session.index < overnight_end]

    prior_date = session_date - dt.timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= dt.timedelta(days=1)
    prior_session_start = dt.datetime.combine(
        prior_date - dt.timedelta(days=1),
        dt.time.fromisoformat(config.OVERNIGHT_START_ET),
        tzinfo=config.TZ_ET,
    )
    prior_session_end = dt.datetime.combine(prior_date, dt.time(17), tzinfo=config.TZ_ET)
    prior_rth_start = dt.datetime.combine(prior_date, dt.time(9, 30), tzinfo=config.TZ_ET)
    prior_rth_end = dt.datetime.combine(prior_date, dt.time(16), tzinfo=config.TZ_ET)
    prior_session = _window(bars_1m, prior_session_start, prior_session_end)
    prior_rth = _window(bars_1m, prior_rth_start, prior_rth_end)
    if prior_session.empty or prior_rth.empty:
        raise RuntimeError(f"No prior-session bars found for {prior_date}")

    rth = session.loc[session.index >= cash_open]

    levels = {
        "session_date": session_date.isoformat(),
        "onh": overnight["High"].max() if not overnight.empty else None,
        "onl": overnight["Low"].min() if not overnight.empty else None,
        "full_session_high": prior_session["High"].max(),
        "full_session_low": prior_session["Low"].min(),
        "rth_high": prior_rth["High"].max(),
        "rth_low": prior_rth["Low"].min(),
    }

    for minutes in config.ORB_WINDOWS_MIN:
        window_end = cash_open + dt.timedelta(minutes=minutes)
        window = rth.loc[rth.index < window_end]
        levels[f"orb{minutes}_high"] = window["High"].max() if not window.empty else None
        levels[f"orb{minutes}_low"] = window["Low"].min() if not window.empty else None

    return levels


def render_chart(bars: pd.DataFrame, symbol: str, interval_label: str, levels: dict, out_path: str):
    hlines, colors, styles = [], [], []
    level_specs = [
        ("onh", "ONH", "tab:red", "--"),
        ("onl", "ONL", "tab:red", "--"),
        ("rth_high", "PDH (RTH)", "tab:blue", "-"),
        ("rth_low", "PDL (RTH)", "tab:blue", "-"),
        ("full_session_high", "PDH (full)", "tab:gray", ":"),
        ("full_session_low", "PDL (full)", "tab:gray", ":"),
        ("orb15_high", "ORB15 H", "tab:green", "--"),
        ("orb15_low", "ORB15 L", "tab:green", "--"),
        ("orb30_high", "ORB30 H", "tab:purple", "--"),
        ("orb30_low", "ORB30 L", "tab:purple", "--"),
    ]
    for key, _label, color, style in level_specs:
        v = levels.get(key)
        if v is not None:
            hlines.append(v)
            colors.append(color)
            styles.append(style)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    mpf.plot(
        bars,
        type="candle",
        volume=True,
        style="yahoo",
        title=f"{symbol} {interval_label} -- {levels['session_date']}",
        hlines=dict(hlines=hlines, colors=colors, linestyle=styles) if hlines else None,
        figsize=(16, 9),
        savefig=out_path,
    )


def append_stats_row(levels: dict, symbol: str, path: str):
    row = {"symbol": symbol, **levels}
    file_exists = os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def write_bars_csv(bars: pd.DataFrame, symbol: str, session_date: dt.date):
    day_dir = os.path.join(config.ARCHIVE_DIR, session_date.isoformat())
    os.makedirs(day_dir, exist_ok=True)
    out_path = os.path.join(day_dir, f"{symbol}_1m.csv")
    bars.to_csv(out_path)
    return out_path


def read_archived_bars(symbol: str, archive_file: str | None = None) -> pd.DataFrame:
    """Load a committed downloader snapshot and normalize its timestamp index."""
    path = Path(archive_file) if archive_file else max(
        Path(config.ARCHIVE_DIR, symbol).glob(f"{symbol}_1m_*.csv")
    )
    bars = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    bars.index = pd.DatetimeIndex(bars.index).tz_convert(config.TZ_ET)
    return bars


def generate_archived_charts(session_date: dt.date, output_dir: str) -> list[str]:
    """Generate the four deterministic ES/NQ charts from committed snapshots."""
    outputs = []
    for symbol in ("ES", "NQ"):
        bars_1m = read_archived_bars(symbol)
        levels = compute_levels(bars_1m, session_date)
        session_bars = bars_1m.loc[session_date_index(bars_1m, session_date)]
        for rule in config.RENDER_INTERVALS:
            out_path = os.path.join(output_dir, f"{symbol}_{rule}.png")
            render_chart(resample(session_bars, rule), symbol, rule, levels, out_path)
            outputs.append(out_path)
            print(f"Wrote {out_path}")
        print(f"{symbol} levels: {levels}")
    return outputs


def run(symbols: list[str], session_date: dt.date):
    for symbol in symbols:
        ticker = config.SYMBOLS[symbol]
        bars_1m = fetch_1m_bars(ticker)
        write_bars_csv(bars_1m, symbol, session_date)

        levels = compute_levels(bars_1m, session_date)
        append_stats_row(
            levels, symbol, os.path.join(config.ARCHIVE_DIR, config.STATS_FILE)
        )

        idx = session_date_index(bars_1m, session_date)
        session_bars = bars_1m.loc[idx]
        for rule in config.RENDER_INTERVALS:
            resampled = resample(session_bars, rule)
            out_path = os.path.join(
                config.ARCHIVE_DIR,
                session_date.isoformat(),
                config.CHARTS_SUBDIR,
                f"{symbol}_{rule}.png",
            )
            render_chart(resampled, symbol, rule, levels, out_path)
            print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, default=None, help="Session date YYYY-MM-DD (default: today, PT)")
    parser.add_argument("--symbol", type=str, choices=list(config.SYMBOLS) + ["ALL"], default="ALL")
    parser.add_argument("--from-archive", action="store_true", help="Generate ES/NQ charts from committed CSV snapshots")
    parser.add_argument("--output-dir", default=None, help="Output directory for --from-archive")
    args = parser.parse_args()

    if args.date:
        session_date = dt.date.fromisoformat(args.date)
    else:
        session_date = dt.datetime.now(config.TZ_PT).date()

    if args.from_archive:
        output_dir = args.output_dir or os.path.join(
            config.ARCHIVE_DIR, session_date.isoformat(), config.CHARTS_SUBDIR
        )
        generate_archived_charts(session_date, output_dir)
    else:
        symbols = list(config.SYMBOLS) if args.symbol == "ALL" else [args.symbol]
        run(symbols, session_date)


if __name__ == "__main__":
    main()
