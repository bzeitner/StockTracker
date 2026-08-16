"""Tests for the per-ticker bar downloader (idea #6 next action)."""
import os
from unittest.mock import patch

import pandas as pd

import config
import download_bars


def _fake_bars() -> pd.DataFrame:
    index = pd.date_range("2026-08-10 09:30", periods=3, freq="1min", tz="America/New_York")
    return pd.DataFrame(
        {
            "Open": [1.0, 2.0, 3.0],
            "High": [1.5, 2.5, 3.5],
            "Low": [0.5, 1.5, 2.5],
            "Close": [1.2, 2.2, 3.2],
            "Volume": [10, 20, 30],
        },
        index=index,
    )


def test_download_ticker_writes_to_per_ticker_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path / "archive"))

    with patch.object(download_bars, "fetch_1m_bars", return_value=_fake_bars()) as mock_fetch:
        out_path = download_bars.download_ticker("NIY", lookback_days=7)

    mock_fetch.assert_called_once_with(config.SYMBOLS["NIY"], lookback_days=7)
    assert os.path.exists(out_path)
    assert out_path.startswith(str(tmp_path / "archive" / "NIY"))

    written = pd.read_csv(out_path)
    assert len(written) == 3


def test_run_downloads_all_configured_symbols_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVE_DIR", str(tmp_path / "archive"))

    with patch.object(download_bars, "fetch_1m_bars", return_value=_fake_bars()):
        out_paths = download_bars.run(list(config.SYMBOLS))

    assert len(out_paths) == len(config.SYMBOLS) == 6
    for symbol, out_path in zip(config.SYMBOLS, out_paths):
        assert os.path.join(str(tmp_path / "archive"), symbol) in out_path
