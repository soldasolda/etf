from __future__ import annotations

from statistics import mean

from app.models import DailyPrice


def moving_average(prices: list[DailyPrice], window: int) -> float:
    if len(prices) < window:
        return mean([item.close for item in prices])
    return mean([item.close for item in prices[-window:]])


def return_pct(prices: list[DailyPrice], window: int) -> float:
    if len(prices) <= window:
        return 0.0
    start = prices[-window - 1].close
    end = prices[-1].close
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100


def volume_change_ratio(prices: list[DailyPrice]) -> float:
    if len(prices) < 25:
        return 1.0
    recent = mean([item.volume for item in prices[-5:]])
    baseline = mean([item.volume for item in prices[-25:-5]])
    if baseline == 0:
        return 1.0
    return recent / baseline
