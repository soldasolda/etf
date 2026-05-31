from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.brokers.base import BrokerClient
from app.charting import create_price_chart
from app.config import Settings
from app.dca import create_base_dca_proposal_if_due, create_tactical_proposal, load_monthly_plan
from app.models import Signal
from app.storage import Storage
from app.strategy import evaluate_signal


@dataclass(frozen=True)
class MonitorResult:
    signal: Signal
    proposal_id: int | None
    chart_path: Path | None
    should_notify: bool
    reason: str


def check_market_once(storage: Storage, client: BrokerClient, settings: Settings) -> MonitorResult:
    prices = client.get_daily_prices(settings.etf_symbol)
    storage.upsert_prices(settings.etf_symbol, prices)
    stored_prices = storage.get_prices(settings.etf_symbol, limit=220)
    plan = load_monthly_plan(storage, settings.default_investment_settings, stored_prices[-1].close)
    signal = evaluate_signal(stored_prices, plan.settings.tactical_budget)
    storage.save_signal(settings.etf_symbol, signal)

    chart_path = create_price_chart(
        stored_prices,
        signal,
        settings.etf_symbol,
        settings.etf_name,
        settings.chart_dir,
    )

    base_proposal_id = create_base_dca_proposal_if_due(
        storage,
        settings.etf_symbol,
        settings.etf_name,
        signal,
        plan,
        stored_prices,
    )
    if base_proposal_id is not None:
        return MonitorResult(
            signal=signal,
            proposal_id=base_proposal_id,
            chart_path=chart_path,
            should_notify=True,
            reason="정기 적립일이 되어 기본 DCA 제안을 생성했습니다.",
        )

    proposal_id, reason = create_tactical_proposal(
        storage,
        settings.etf_symbol,
        settings.etf_name,
        signal,
        plan,
        settings.monitor_min_score,
        settings.monitor_cooldown_minutes,
    )
    return MonitorResult(
        signal=signal,
        proposal_id=proposal_id,
        chart_path=chart_path,
        should_notify=proposal_id is not None,
        reason=reason,
    )
