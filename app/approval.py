from __future__ import annotations

from app.brokers.base import BrokerClient
from app.config import Settings
from app.storage import Storage


def approve_proposal(storage: Storage, client: BrokerClient, settings: Settings, proposal_id: int) -> str:
    proposal = storage.get_proposal(proposal_id)
    if proposal is None:
        return f"제안 {proposal_id}번을 찾지 못했습니다."
    if proposal.status != "pending":
        return f"제안 {proposal_id}번은 이미 '{proposal.status}' 상태입니다."

    prices = client.get_daily_prices(proposal.symbol)
    current_price = prices[-1].close
    drift_pct = (current_price / proposal.proposed_price - 1.0) * 100
    if abs(drift_pct) > settings.approval_max_price_drift_pct:
        note = f"가격 변동률 {drift_pct:+.2f}%로 재승인 필요"
        storage.decide_proposal(proposal_id, "expired", note)
        return f"가격이 승인 기준보다 많이 변했습니다. ({drift_pct:+.2f}%) 리포트를 다시 생성해주세요."

    if proposal.proposed_amount > settings.daily_max_order_amount:
        note = f"일일 주문 상한 초과: {proposal.proposed_amount:,}원"
        storage.decide_proposal(proposal_id, "blocked", note)
        return f"일일 주문 상한을 초과해 차단했습니다. 제안 금액: {proposal.proposed_amount:,}원"

    note = f"승인됨. 현재 버전은 주문 전송 없이 승인 기록만 저장합니다. 재조회 가격 {current_price:,}원"
    storage.decide_proposal(proposal_id, "approved", note)
    return (
        f"제안 {proposal_id}번을 승인했습니다.\n"
        f"수량: {proposal.proposed_quantity:,}주\n"
        f"금액: {proposal.proposed_amount:,}원\n"
        "현재 버전은 실전/모의 주문을 보내지 않고 승인 기록만 저장합니다."
    )


def reject_proposal(storage: Storage, proposal_id: int) -> str:
    proposal = storage.get_proposal(proposal_id)
    if proposal is None:
        return f"제안 {proposal_id}번을 찾지 못했습니다."
    if proposal.status != "pending":
        return f"제안 {proposal_id}번은 이미 '{proposal.status}' 상태입니다."
    storage.decide_proposal(proposal_id, "rejected", "사용자 거절")
    return f"제안 {proposal_id}번을 거절했습니다."
