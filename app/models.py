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
    buy_ratio: float
    tactical_amount: int
    expected_quantity: int
    current_price: int
    avg_3m: float
    ma20: float
    ma60: float
    discount_pct: float
    five_day_return_pct: float
    reasons: list[str]


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
    side: str
    symbol: str
    name: str
    trade_date: date
    price: int
    quantity: int
    amount: int
    fee: int
    created_at: datetime
