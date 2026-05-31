from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.brokers.base import BrokerClient
from app.charting import create_price_chart
from app.config import Settings
from app.models import Signal
from app.storage import Storage
from app.strategy import evaluate_signal


@dataclass(frozen=True)
class DailyReportResult:
    signal: Signal
    proposal_id: int | None
    chart_path: Path | None


def create_daily_report(storage: Storage, client: BrokerClient, settings: Settings) -> DailyReportResult:
    prices = client.get_daily_prices(settings.etf_symbol)
    storage.upsert_prices(settings.etf_symbol, prices)
    stored_prices = storage.get_prices(settings.etf_symbol, limit=120)
    signal = evaluate_signal(stored_prices, settings.tactical_budget)
    storage.save_signal(settings.etf_symbol, signal)
    proposal_id = storage.create_proposal(settings.etf_symbol, settings.etf_name, signal)
    chart_path = create_price_chart(
        stored_prices,
        signal,
        settings.etf_symbol,
        settings.etf_name,
        settings.chart_dir,
    )
    return DailyReportResult(signal=signal, proposal_id=proposal_id, chart_path=chart_path)
