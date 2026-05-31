from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.brokers.base import BrokerClient
from app.charting import create_price_chart
from app.config import Settings
from app.dca import MonthlyPlan, create_base_dca_proposal_if_due, create_tactical_proposal, load_monthly_plan
from app.models import DailyPrice, Signal
from app.storage import Storage
from app.strategy import evaluate_signal


@dataclass(frozen=True)
class DailyReportResult:
    signal: Signal
    proposal_ids: list[int]
    chart_path: Path | None
    recent_prices: list[DailyPrice]
    monthly_plan: MonthlyPlan


def create_daily_report(storage: Storage, client: BrokerClient, settings: Settings) -> DailyReportResult:
    prices = client.get_daily_prices(settings.etf_symbol)
    storage.upsert_prices(settings.etf_symbol, prices)
    stored_prices = storage.get_prices(settings.etf_symbol, limit=220)
    initial_price = stored_prices[-1].close
    plan = load_monthly_plan(storage, settings.default_investment_settings, initial_price)
    signal = evaluate_signal(stored_prices, plan.settings.tactical_budget)
    storage.save_signal(settings.etf_symbol, signal)
    proposal_ids: list[int] = []
    base_proposal_id = create_base_dca_proposal_if_due(
        storage,
        settings.etf_symbol,
        settings.etf_name,
        signal,
        plan,
        stored_prices,
    )
    if base_proposal_id is not None:
        proposal_ids.append(base_proposal_id)
    tactical_proposal_id, _ = create_tactical_proposal(
        storage,
        settings.etf_symbol,
        settings.etf_name,
        signal,
        plan,
        settings.monitor_min_score,
        settings.monitor_cooldown_minutes,
    )
    if tactical_proposal_id is not None:
        proposal_ids.append(tactical_proposal_id)
    plan = load_monthly_plan(storage, settings.default_investment_settings, signal.current_price)
    chart_path = create_price_chart(
        stored_prices,
        signal,
        settings.etf_symbol,
        settings.etf_name,
        settings.chart_dir,
    )
    return DailyReportResult(
        signal=signal,
        proposal_ids=proposal_ids,
        chart_path=chart_path,
        recent_prices=stored_prices[-7:],
        monthly_plan=plan,
    )
