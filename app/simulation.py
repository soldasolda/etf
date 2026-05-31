from __future__ import annotations

from app.models import Proposal
from app.storage import Storage


def execute_simulated_buy(
    storage: Storage,
    proposal: Proposal,
    current_price: int,
    initial_cash: int,
) -> str:
    storage.ensure_simulation_account(initial_cash)
    quantity = proposal.proposed_quantity
    amount = current_price * quantity
    fee = calculate_fee(amount)
    account, position = storage.buy_simulation_position(
        proposal_id=proposal.id,
        symbol=proposal.symbol,
        name=proposal.name,
        price=current_price,
        quantity=quantity,
        fee=fee,
    )
    return (
        "시뮬레이션 매수가 완료되었습니다.\n"
        f"종목: {proposal.name} ({proposal.symbol})\n"
        f"체결가: {current_price:,}원\n"
        f"수량: {quantity:,}주\n"
        f"체결금액: {amount:,}원\n"
        f"수수료: {fee:,}원\n"
        f"남은 현금: {account.cash:,}원\n"
        f"보유수량: {position.quantity:,}주\n"
        f"평균단가: {position.avg_price:,.0f}원"
    )


def calculate_fee(amount: int) -> int:
    return 0
