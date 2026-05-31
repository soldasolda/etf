from __future__ import annotations

import random
from datetime import date, timedelta

from app.models import DailyPrice


class SampleBrokerClient:
    name = "sample"

    def get_daily_prices(self, symbol: str) -> list[DailyPrice]:
        return sample_daily_prices()


def sample_daily_prices(days: int = 120) -> list[DailyPrice]:
    rng = random.Random(20260531)
    today = date.today()
    price = 18000
    prices: list[DailyPrice] = []
    cursor = today - timedelta(days=days * 2)
    while len(prices) < days:
        cursor += timedelta(days=1)
        if cursor.weekday() >= 5:
            continue
        drift = 0.0008
        noise = rng.uniform(-0.018, 0.016)
        if len(prices) > days - 12:
            noise -= 0.006
        price = max(1000, int(price * (1 + drift + noise)))
        open_price = int(price * (1 + rng.uniform(-0.006, 0.006)))
        high = max(open_price, price) + rng.randint(20, 140)
        low = min(open_price, price) - rng.randint(20, 140)
        prices.append(
            DailyPrice(
                trade_date=cursor,
                open=open_price,
                high=high,
                low=max(1, low),
                close=price,
                volume=rng.randint(120000, 600000),
            )
        )
    return prices
