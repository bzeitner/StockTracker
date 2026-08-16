#!/usr/bin/env python3
"""
Bulk 1-minute bar downloader (idea #6 next action): for each configured
ticker, pull the last 7 days of 1-minute bars from yfinance and write them
into a per-ticker folder under the archive.

This is separate from daily_chart.py's per-session snapshot: daily_chart.py
renders one session's chart/levels, while this script just backfills the
raw 1-minute history yfinance currently has available (capped at 7 calendar
days -- see README "Known limitations") into `archive/<TICKER>/`, one file
per ticker per run.

Usage:
    python download_bars.py                 # all configured tickers
    python download_bars.py --symbol NIY     # single ticker
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

import config
from daily_chart import fetch_1m_bars


def download_ticker(symbol: str, lookback_days: int = 7) -> str:
    """Fetch the last `lookback_days` of 1-minute bars for `symbol` and
    write them to `archive/<symbol>/<symbol>_1m_<fetched-date>.csv`.

    Returns the output path.
    """
    ticker = config.SYMBOLS[symbol]
    bars = fetch_1m_bars(ticker, lookback_days=lookback_days)

    ticker_dir = os.path.join(config.ARCHIVE_DIR, symbol)
    os.makedirs(ticker_dir, exist_ok=True)

    fetched_date = dt.datetime.now(config.TZ_PT).date().isoformat()
    out_path = os.path.join(ticker_dir, f"{symbol}_1m_{fetched_date}.csv")
    bars.to_csv(out_path)
    return out_path


def run(symbols: list[str]) -> list[str]:
    out_paths = []
    for symbol in symbols:
        out_path = download_ticker(symbol)
        print(f"Wrote {out_path}")
        out_paths.append(out_path)
    return out_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbol",
        type=str,
        choices=list(config.SYMBOLS) + ["ALL"],
        default="ALL",
    )
    args = parser.parse_args()
    symbols = list(config.SYMBOLS) if args.symbol == "ALL" else [args.symbol]
    run(symbols)


if __name__ == "__main__":
    main()
