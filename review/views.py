import datetime as dt

from django.http import JsonResponse
from django.shortcuts import render

import config
from review import services


def index(request):
    tickers = services.available_tickers()
    ranges = {}
    for symbol in tickers:
        try:
            start, end = services.available_range(symbol)
            ranges[symbol] = {"start": start.isoformat(), "end": end.isoformat()}
        except services.ReviewError:
            continue
    return render(
        request,
        "review/index.html",
        {
            "tickers": tickers,
            "ranges": ranges,
            "orb_defaults": list(config.ORB_WINDOWS_MIN),
        },
    )


def _parse_date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise services.ReviewError(f"Invalid {field} '{value}', expected YYYY-MM-DD")


def api_chart_data(request):
    symbol = request.GET.get("symbol", "")
    start_raw = request.GET.get("start", "")
    end_raw = request.GET.get("end", "")
    interval_raw = request.GET.get("interval", "1")
    orb_raw = request.GET.get("orb")

    try:
        start_date = _parse_date(start_raw, "start")
        end_date = _parse_date(end_raw, "end")
        try:
            interval_minutes = int(interval_raw)
        except (TypeError, ValueError):
            raise services.ReviewError(f"Invalid interval '{interval_raw}'")
        if interval_minutes not in (1, 2, 5):
            raise services.ReviewError("interval must be 1, 2, or 5")
        orb_minutes = int(orb_raw) if orb_raw not in (None, "") else None

        bars = services.get_chart_data(symbol, start_date, end_date, interval_minutes)
        levels = services.get_levels(symbol, end_date, orb_minutes)
    except services.ReviewError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"symbol": symbol, "interval": interval_minutes, "bars": bars, "levels": levels})
