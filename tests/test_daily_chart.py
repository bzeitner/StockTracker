import datetime as dt
from pathlib import Path

import pandas as pd

import config
import daily_chart


def _bars():
    index = pd.date_range("2026-08-26 18:00", "2026-08-28 16:59", freq="1min", tz=config.TZ_ET)
    values = pd.Series(range(len(index)), index=index, dtype=float)
    return pd.DataFrame({
        "Open": values, "High": values + 2, "Low": values - 2,
        "Close": values + 1, "Volume": 10,
    }, index=index)


def test_compute_levels_uses_prior_session_and_opening_ranges():
    bars = _bars()
    levels = daily_chart.compute_levels(bars, dt.date(2026, 8, 28))
    assert levels["full_session_high"] == bars.loc["2026-08-26 18:00":"2026-08-27 16:59", "High"].max()
    assert levels["rth_high"] == bars.loc["2026-08-27 09:30":"2026-08-27 15:59", "High"].max()
    assert levels["onh"] == bars.loc["2026-08-27 18:00":"2026-08-28 09:29", "High"].max()
    assert levels["orb15_high"] == bars.loc["2026-08-28 09:30":"2026-08-28 09:44", "High"].max()
    assert levels["orb30_low"] == bars.loc["2026-08-28 09:30":"2026-08-28 09:59", "Low"].min()


def test_generate_archived_charts_produces_four_pngs(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_chart, "read_archived_bars", lambda symbol: _bars())
    outputs = daily_chart.generate_archived_charts(dt.date(2026, 8, 28), str(tmp_path))
    assert {Path(path).name for path in outputs} == {
        "ES_2min.png", "ES_5min.png", "NQ_2min.png", "NQ_5min.png"
    }
    assert all(Path(path).stat().st_size > 0 for path in outputs)
