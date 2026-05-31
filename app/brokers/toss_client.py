from __future__ import annotations

from app.config import Settings
from app.models import DailyPrice


class TossBrokerClient:
    name = "toss"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_daily_prices(self, symbol: str) -> list[DailyPrice]:
        raise NotImplementedError(
            "Toss Open API is waiting for approval/documentation. "
            "Use BROKER=sample for reports until the official spec is available."
        )
