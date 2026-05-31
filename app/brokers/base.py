from __future__ import annotations

from typing import Protocol

from app.models import DailyPrice


class BrokerClient(Protocol):
    name: str

    def get_daily_prices(self, symbol: str) -> list[DailyPrice]:
        """Return daily prices ordered from oldest to newest."""
