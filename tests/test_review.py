import datetime as dt

import pandas as pd
import pytest
from django.test import Client

import config
from review import services


def _bars():
    index = pd.date_range("2026-08-26 18:00", "2026-08-28 16:59", freq="1min", tz=config.TZ_ET)
    index.name = "Datetime"
    values = pd.Series(range(len(index)), index=index, dtype=float)
    return pd.DataFrame({
        "Open": values, "High": values + 2, "Low": values - 2,
        "Close": values + 1, "Volume": 10,
    }, index=index)


def _write_snapshot(tmp_path, symbol, fetched_date, bars):
    ticker_dir = tmp_path / symbol
    ticker_dir.mkdir(parents=True, exist_ok=True)
    path = ticker_dir / f"{symbol}_1m_{fetched_date}.csv"
    bars.to_csv(path)
    return path


def test_load_ticker_bars_merges_and_dedupes_overlapping_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path))
    bars = _bars()
    _write_snapshot(tmp_path, "ES", "2026-08-27", bars.iloc[:100])
    updated = bars.copy()
    updated["Close"] = updated["Close"] + 1000  # distinguishable "later fetch" values
    _write_snapshot(tmp_path, "ES", "2026-08-28", updated.iloc[50:])

    merged = services.load_ticker_bars("ES")

    assert merged.index.is_monotonic_increasing
    assert not merged.index.duplicated().any()
    # Overlap region (rows 50-99) must come from the later-fetched file.
    overlap_ts = bars.index[60]
    assert merged.loc[overlap_ts, "Close"] == updated.loc[overlap_ts, "Close"]


def test_load_ticker_bars_rejects_unknown_ticker():
    with pytest.raises(services.ReviewError):
        services.load_ticker_bars("ZZ")


def test_get_chart_data_resamples_to_requested_interval(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path))
    bars = _bars()
    _write_snapshot(tmp_path, "ES", "2026-08-28", bars)

    records = services.get_chart_data("ES", dt.date(2026, 8, 28), dt.date(2026, 8, 28), 5)

    assert len(records) > 0
    assert all(r["low"] <= r["open"] <= r["high"] for r in records)
    assert all(r["low"] <= r["close"] <= r["high"] for r in records)


def test_get_chart_data_rejects_range_outside_collected_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "ES", "2026-08-28", _bars())

    with pytest.raises(services.ReviewError):
        services.get_chart_data("ES", dt.date(2020, 1, 1), dt.date(2020, 1, 2), 1)


def test_get_levels_adds_extra_orb_window_without_changing_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "ES", "2026-08-28", _bars())

    default_levels = services.get_levels("ES", dt.date(2026, 8, 28), None)
    custom_levels = services.get_levels("ES", dt.date(2026, 8, 28), 20)

    assert "orb15_high" in default_levels and "orb30_high" in default_levels
    assert "orb20_high" not in default_levels
    assert custom_levels["orb15_high"] == default_levels["orb15_high"]
    assert "orb20_high" in custom_levels


def test_get_levels_rejects_orb_minutes_out_of_bounds(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path))
    _write_snapshot(tmp_path, "ES", "2026-08-28", _bars())

    with pytest.raises(services.ReviewError):
        services.get_levels("ES", dt.date(2026, 8, 28), 0)


# --- Regression check against the documented, already-reviewed reference ---
# levels for ES 2026-08-28 (README "Reference output for the completed
# 2026-08-28 session", generated and reviewed as part of merged PR #4).
# This is the real committed archive/ES/*.csv data, not a synthetic
# fixture -- it is the closest automatable stand-in for a manual
# TradingView comparison, without requiring an interactive browser.
ES_2026_08_28_REFERENCE = {
    "onh": 7755.00,
    "onl": 7727.25,
    "rth_high": 7755.50,
    "rth_low": 7702.75,
    "full_session_high": 7755.50,
    "full_session_low": 7702.75,
    "orb15_high": 7757.50,
    "orb15_low": 7743.75,
    "orb30_high": 7758.00,
    "orb30_low": 7743.75,
}


def test_get_levels_matches_documented_reference_for_real_archive_data():
    levels = services.get_levels("ES", dt.date(2026, 8, 28), None)
    for key, expected in ES_2026_08_28_REFERENCE.items():
        assert levels[key] == pytest.approx(expected), f"{key}: {levels[key]} != {expected}"


def test_index_view_lists_available_tickers():
    client = Client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"ES" in response.content


def test_api_chart_data_end_to_end_matches_reference():
    client = Client()
    response = client.get(
        "/api/chart-data",
        {"symbol": "ES", "start": "2026-08-28", "end": "2026-08-28", "interval": "5", "orb": "15"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["bars"]) > 0
    assert payload["levels"]["onh"] == pytest.approx(ES_2026_08_28_REFERENCE["onh"])
    assert payload["levels"]["orb15_low"] == pytest.approx(ES_2026_08_28_REFERENCE["orb15_low"])


def test_api_chart_data_rejects_bad_interval():
    client = Client()
    response = client.get(
        "/api/chart-data",
        {"symbol": "ES", "start": "2026-08-28", "end": "2026-08-28", "interval": "3"},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_api_chart_data_rejects_unknown_symbol():
    client = Client()
    response = client.get(
        "/api/chart-data",
        {"symbol": "ZZ", "start": "2026-08-28", "end": "2026-08-28", "interval": "1"},
    )
    assert response.status_code == 400
