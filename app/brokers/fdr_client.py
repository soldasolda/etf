from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.models import DailyPrice


class FinanceDataReaderBrokerClient:
    name = "fdr"

    def __init__(self, days: int = 180) -> None:
        self.days = days

    def get_daily_prices(self, symbol: str) -> list[DailyPrice]:
        try:
            import FinanceDataReader as fdr
        except ImportError as exc:
            raise RuntimeError(
                "FinanceDataReader is not installed. Run: py -3.9 -m pip install -r requirements.txt"
            ) from exc

        start = (date.today() - timedelta(days=self.days * 2)).isoformat()
        frame = fdr.DataReader(symbol, start)
        if frame.empty:
            raise RuntimeError(f"FinanceDataReader returned no price data for symbol: {symbol}")

        prices: list[DailyPrice] = []
        for index, row in frame.tail(self.days).iterrows():
            close = _to_int(row.get("Close"))
            prices.append(
                DailyPrice(
                    trade_date=index.date(),
                    open=_to_int(row.get("Open", close)),
                    high=_to_int(row.get("High", close)),
                    low=_to_int(row.get("Low", close)),
                    close=close,
                    volume=_to_int(row.get("Volume", 0)),
                )
            )
        return prices


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        if value != value:
            return 0
    except TypeError:
        pass
    return abs(int(float(value)))
