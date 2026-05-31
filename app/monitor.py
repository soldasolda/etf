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
class MonitorResult:
    signal: Signal
    proposal_id: int | None
    chart_path: Path | None
    should_notify: bool
    reason: str


def check_market_once(storage: Storage, client: BrokerClient, settings: Settings) -> MonitorResult:
    prices = client.get_daily_prices(settings.etf_symbol)
    storage.upsert_prices(settings.etf_symbol, prices)
    stored_prices = storage.get_prices(settings.etf_symbol, limit=120)
    signal = evaluate_signal(stored_prices, settings.tactical_budget)
    storage.save_signal(settings.etf_symbol, signal)

    chart_path = create_price_chart(
        stored_prices,
        signal,
        settings.etf_symbol,
        settings.etf_name,
        settings.chart_dir,
    )

    if signal.score < settings.monitor_min_score:
        return MonitorResult(
            signal=signal,
            proposal_id=None,
            chart_path=chart_path,
            should_notify=False,
            reason=f"점수 {signal.score}점이 알림 기준 {settings.monitor_min_score}점보다 낮습니다.",
        )

    if signal.expected_quantity <= 0 or signal.tactical_amount <= 0:
        return MonitorResult(
            signal=signal,
            proposal_id=None,
            chart_path=chart_path,
            should_notify=False,
            reason="추천 수량 또는 금액이 0입니다.",
        )

    if storage.has_recent_active_proposal(settings.etf_symbol, settings.monitor_cooldown_minutes):
        return MonitorResult(
            signal=signal,
            proposal_id=None,
            chart_path=chart_path,
            should_notify=False,
            reason="최근 활성 제안이 있어 중복 알림을 건너뜁니다.",
        )

    proposal_id = storage.create_proposal(settings.etf_symbol, settings.etf_name, signal)
    return MonitorResult(
        signal=signal,
        proposal_id=proposal_id,
        chart_path=chart_path,
        should_notify=proposal_id is not None,
        reason="매수 제안 조건을 충족했습니다.",
    )
