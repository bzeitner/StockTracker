"""Tests for the ticker configuration (idea #6 next action)."""
import config


def test_six_tickers_configured():
    assert len(config.SYMBOLS) == 6


def test_at_least_one_ticker_outside_us():
    assert config.NON_US_SYMBOLS, "NON_US_SYMBOLS must be non-empty"
    assert config.NON_US_SYMBOLS.issubset(config.SYMBOLS.keys())


def test_non_us_symbols_are_a_subset_of_all_symbols():
    # Sanity check: every non-US symbol must actually be a configured ticker.
    for symbol in config.NON_US_SYMBOLS:
        assert symbol in config.SYMBOLS
