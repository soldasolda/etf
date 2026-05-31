from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DailyPrice:
    trade_date: date
    open: int
    high: int
    low: int
    close: int
    volume: int


@dataclass(frozen=True)
class Signal:
    score: int
    label: str
    health_score: int
    health_label: str
    tactical_score: int
    tactical_label: str
    buy_ratio: float
    tactical_amount: int
    expected_quantity: int
    current_price: int
    avg_3m: float
    avg_3w: float
    ma20: float
    ma60: float
    ma120: float
    discount_pct: float
    three_week_position_pct: float
    pullback_from_3w_high_pct: float
    range_position_120d_pct: float
    pullback_from_120d_high_pct: float
    rsi14: float
    five_day_return_pct: float
    reasons: list[str]
    score_details: list[str]
    health_details: list[str]
    tactical_details: list[str]


@dataclass(frozen=True)
class Proposal:
    id: int
    symbol: str
    name: str
    created_at: datetime
    status: str
    proposed_price: int
    proposed_amount: int
    proposed_quantity: int
    score: int
    label: str
    proposal_type: str
    cycle_month: str | None


@dataclass(frozen=True)
class InvestmentSettings:
    total_budget: int
    base_budget: int
    tactical_budget: int
    dca_day: int


@dataclass(frozen=True)
class SimulationAccount:
    cash: int
    initial_cash: int
    updated_at: datetime


@dataclass(frozen=True)
class SimulationPosition:
    symbol: str
    name: str
    quantity: int
    avg_price: float
    invested_amount: int
    updated_at: datetime


@dataclass(frozen=True)
class SimulationTrade:
    id: int
    proposal_id: int | None
    proposal_type: str
    cycle_month: str | None
    side: str
    symbol: str
    name: str
    trade_date: date
    price: int
    quantity: int
    amount: int
    fee: int
    created_at: datetime
