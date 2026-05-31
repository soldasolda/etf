from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from app.models import DailyPrice, InvestmentSettings, Signal
from app.storage import Storage


BASE_DCA_TYPE = "base_dca"
TACTICAL_TYPE = "tactical"


@dataclass(frozen=True)
class MonthlyPlan:
    cycle_month: str
    settings: InvestmentSettings
    tactical_spent: int
    tactical_remaining: int
    days_left: int
    benchmark_summary: str | None


@dataclass(frozen=True)
class TacticalDecision:
    target_amount: int
    quantity: int
    amount: int
    ratio: float
    label: str
    reasons: list[str]
    should_notify: bool


def current_cycle_month(today: date | None = None) -> str:
    today = today or date.today()
    return today.strftime("%Y-%m")


def days_left_in_month(today: date | None = None) -> int:
    today = today or date.today()
    last_day = monthrange(today.year, today.month)[1]
    return last_day - today.day


def load_monthly_plan(
    storage: Storage,
    defaults: InvestmentSettings,
    current_price: int,
    today: date | None = None,
) -> MonthlyPlan:
    today = today or date.today()
    investment = normalize_investment_settings(storage.get_investment_settings(defaults))
    cycle_month = current_cycle_month(today)
    tactical_spent = storage.get_monthly_tactical_spent(cycle_month)
    tactical_remaining = max(0, investment.tactical_budget - tactical_spent)
    benchmark_summary = storage.get_benchmark_summary(cycle_month, current_price)
    return MonthlyPlan(
        cycle_month=cycle_month,
        settings=investment,
        tactical_spent=tactical_spent,
        tactical_remaining=tactical_remaining,
        days_left=days_left_in_month(today),
        benchmark_summary=benchmark_summary,
    )


def normalize_investment_settings(settings: InvestmentSettings) -> InvestmentSettings:
    total_budget = max(0, settings.total_budget)
    dca_day = min(28, max(1, settings.dca_day))
    base_budget = min(max(0, settings.base_budget), total_budget)
    tactical_budget = min(max(0, settings.tactical_budget), total_budget - base_budget)
    if base_budget + tactical_budget < total_budget:
        tactical_budget = total_budget - base_budget
    return InvestmentSettings(
        total_budget=total_budget,
        base_budget=base_budget,
        tactical_budget=tactical_budget,
        dca_day=dca_day,
    )


def create_base_dca_proposal_if_due(
    storage: Storage,
    symbol: str,
    name: str,
    signal: Signal,
    plan: MonthlyPlan,
    prices: list[DailyPrice] | None = None,
    today: date | None = None,
) -> int | None:
    today = today or date.today()
    if today.day < plan.settings.dca_day:
        return None
    benchmark_date, benchmark_price = benchmark_price_for_cycle(prices or [], plan.settings, today, signal.current_price)
    storage.ensure_benchmark_cycle(
        cycle_month=plan.cycle_month,
        symbol=symbol,
        name=name,
        benchmark_date=benchmark_date,
        price=benchmark_price,
        total_budget=plan.settings.total_budget,
    )
    if storage.has_cycle_proposal(symbol, plan.cycle_month, BASE_DCA_TYPE):
        return None
    quantity = plan.settings.base_budget // signal.current_price if signal.current_price > 0 else 0
    amount = quantity * signal.current_price
    return storage.create_proposal(
        symbol,
        name,
        signal,
        proposal_type=BASE_DCA_TYPE,
        cycle_month=plan.cycle_month,
        amount_override=amount,
        quantity_override=quantity,
    )


def create_tactical_proposal(
    storage: Storage,
    symbol: str,
    name: str,
    signal: Signal,
    plan: MonthlyPlan,
    min_score: int,
    cooldown_minutes: int,
) -> tuple[int | None, str]:
    decision = decide_tactical_buy(signal, plan, min_score)
    if plan.tactical_remaining <= 0:
        return None, decision.label
    if storage.has_recent_active_proposal(symbol, cooldown_minutes, TACTICAL_TYPE, plan.cycle_month):
        return None, "최근 전술 제안이 있어 중복 알림을 건너뜁니다."
    if not decision.should_notify:
        return None, decision.label
    if decision.quantity <= 0 or decision.amount <= 0:
        return None, "남은 전술 자금으로 살 수 있는 수량이 없습니다."

    proposal_id = storage.create_proposal(
        symbol,
        name,
        signal,
        proposal_type=TACTICAL_TYPE,
        cycle_month=plan.cycle_month,
        amount_override=decision.amount,
        quantity_override=decision.quantity,
    )
    if proposal_id is None:
        return None, "전술 제안을 생성하지 못했습니다."
    return proposal_id, decision.label


def decide_tactical_buy(signal: Signal, plan: MonthlyPlan, min_score: int) -> TacticalDecision:
    reasons: list[str] = []
    if plan.tactical_remaining <= 0:
        return TacticalDecision(0, 0, 0, 0.0, "이번 달 전술 자금을 모두 사용했습니다.", reasons, False)

    healthy_uptrend = is_healthy_uptrend(signal)
    damaged_trend = is_damaged_trend(signal)
    overheated = is_overheated(signal)
    month_end = plan.days_left <= 5

    base_ratio = signal.buy_ratio
    if healthy_uptrend:
        base_ratio = max(base_ratio, 0.2)
        reasons.append("장기 상승 추세가 살아 있어 전술 자금 0%를 피합니다.")
    if overheated:
        base_ratio = min(base_ratio, 0.3)
        reasons.append("가격은 고점권이라 전술 자금을 한 번에 많이 쓰지 않습니다.")
    if damaged_trend and not month_end:
        base_ratio = min(base_ratio, 0.1)
        reasons.append("추세 훼손 구간이라 월말 전까지는 전술 자금을 보수적으로 씁니다.")

    if signal.tactical_score < min_score and signal.health_score < 75 and not month_end:
        return TacticalDecision(
            0,
            0,
            0,
            0.0,
            f"전술 매력도 {signal.tactical_score}점이 기준 {min_score}점보다 낮고 건강도도 부족합니다.",
            reasons,
            False,
        )

    if month_end:
        target_amount = plan.tactical_remaining
        reasons.append("월말 소진 원칙에 따라 남은 전술 자금 전체를 제안합니다.")
    else:
        target_amount = int(plan.settings.tactical_budget * base_ratio)
        target_amount = min(target_amount, plan.tactical_remaining)

    quantity = target_amount // signal.current_price if signal.current_price > 0 else 0
    amount = quantity * signal.current_price
    ratio = amount / plan.settings.tactical_budget if plan.settings.tactical_budget else 0.0
    if amount <= 0:
        return TacticalDecision(target_amount, 0, 0, ratio, "전술 자금으로 살 수 있는 최소 수량이 없습니다.", reasons, False)

    if month_end:
        label = "월말 소진 원칙으로 전술 매수 제안을 생성했습니다."
    elif healthy_uptrend and signal.tactical_score < min_score:
        label = "상승 추세 참여 원칙으로 최소 전술 매수 제안을 생성했습니다."
    else:
        label = "전술 매수 제안 조건을 충족했습니다."
    return TacticalDecision(target_amount, quantity, amount, ratio, label, reasons, True)


def is_healthy_uptrend(signal: Signal) -> bool:
    return signal.health_score >= 75 and signal.current_price > signal.ma20 > signal.ma60


def is_damaged_trend(signal: Signal) -> bool:
    return signal.current_price < signal.ma120 and signal.ma20 <= signal.ma60


def is_overheated(signal: Signal) -> bool:
    return signal.rsi14 >= 70 and signal.range_position_120d_pct >= 90 and signal.discount_pct > 5


def benchmark_price_for_cycle(
    prices: list[DailyPrice],
    settings: InvestmentSettings,
    today: date,
    fallback_price: int,
) -> tuple[date, int]:
    target_date = date(today.year, today.month, settings.dca_day)
    for item in prices:
        if item.trade_date >= target_date:
            return item.trade_date, item.close
    return today, fallback_price
