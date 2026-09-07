"""
Read-only data layer for the ticker review viewer (idea #79).

Reads the same committed per-ticker archive CSVs that `download_bars.py`
writes (`archive/<TICKER>/<TICKER>_1m_<fetched-date>.csv`) and reuses
`daily_chart`'s resampling and level-calculation logic so the review
viewer can never disagree with the daily snapshot chart about what a
level means.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

import config
import daily_chart

MAX_RANGE_DAYS = 60


class ReviewError(ValueError):
    """Raised for invalid ticker/date-range requests; callers turn this into a 4xx."""


def available_tickers() -> list[str]:
    return sorted(
        symbol
        for symbol in config.SYMBOLS
        if list(Path(config.ARCHIVE_DIR, symbol).glob(f"{symbol}_1m_*.csv"))
    )


def load_ticker_bars(symbol: str) -> pd.DataFrame:
    """Load and merge every committed snapshot for `symbol` into one
    de-duplicated, sorted 1-minute bar series.

    Each snapshot file is a rolling last-7-days pull, so consecutive
    files overlap; keep the most recently fetched value for any
    duplicated timestamp.
    """
    if symbol not in config.SYMBOLS:
        raise ReviewError(f"Unknown ticker '{symbol}'")

    paths = sorted(Path(config.ARCHIVE_DIR, symbol).glob(f"{symbol}_1m_*.csv"))
    if not paths:
        raise ReviewError(f"No archived data for ticker '{symbol}'")

    frames = []
    for path in paths:
        bars = pd.read_csv(path, index_col="Datetime", parse_dates=True)
        bars.index = pd.DatetimeIndex(bars.index).tz_convert(config.TZ_ET)
        frames.append(bars)

    merged = pd.concat(frames)
    merged = merged[~merged.index.duplicated(keep="last")]
    merged = merged.sort_index()
    return merged


def available_range(symbol: str) -> tuple[dt.date, dt.date]:
    bars = load_ticker_bars(symbol)
    return bars.index.min().date(), bars.index.max().date()


def get_chart_data(symbol: str, start_date: dt.date, end_date: dt.date, interval_minutes: int) -> list[dict]:
    """Resampled OHLCV bars for [start_date, end_date] (inclusive, ET calendar days)."""
    if start_date > end_date:
        raise ReviewError("start_date must not be after end_date")
    if (end_date - start_date).days > MAX_RANGE_DAYS:
        raise ReviewError(f"Range exceeds the {MAX_RANGE_DAYS}-day maximum")

    bars = load_ticker_bars(symbol)
    data_start, data_end = bars.index.min().date(), bars.index.max().date()
    if end_date < data_start or start_date > data_end:
        raise ReviewError(
            f"Requested range {start_date}..{end_date} is outside the collected "
            f"data range {data_start}..{data_end}"
        )

    window_start = dt.datetime.combine(start_date, dt.time.min, tzinfo=config.TZ_ET)
    window_end = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time.min, tzinfo=config.TZ_ET)
    windowed = bars.loc[(bars.index >= window_start) & (bars.index < window_end)]
    if windowed.empty:
        return []

    resampled = daily_chart.resample(windowed, f"{interval_minutes}min")
    records = []
    for ts, row in resampled.iterrows():
        records.append(
            {
                "time": int(ts.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
    return records


def get_levels(symbol: str, session_date: dt.date, orb_minutes: int | None) -> dict:
    """Session levels for `session_date`, per `daily_chart.compute_levels`,
    plus an extra ORB window for `orb_minutes` when it isn't already one
    of `config.ORB_WINDOWS_MIN`.
    """
    bars = load_ticker_bars(symbol)
    extra = None
    if orb_minutes is not None:
        if orb_minutes < 1 or orb_minutes > 120:
            raise ReviewError("orb_minutes must be between 1 and 120")
        if orb_minutes not in config.ORB_WINDOWS_MIN:
            extra = [orb_minutes]
    try:
        return daily_chart.compute_levels(bars, session_date, extra_orb_minutes=extra)
    except RuntimeError as exc:
        raise ReviewError(str(exc)) from exc
