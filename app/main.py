from __future__ import annotations

import argparse
import time

from app.approval import approve_proposal, reject_proposal
from app.brokers import create_broker_client
from app.config import load_settings
from app.monitor import check_market_once
from app.report_service import create_daily_report
from app.reporting import render_daily_report
from app.storage import Storage
from app.telegram_bot import run_telegram_bot


def main() -> None:
    parser = argparse.ArgumentParser(description="ETF 적립 매수 보조 시스템")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="저장소를 초기화합니다.")
    subparsers.add_parser("report", help="일일 리포트와 승인 대기 제안을 생성합니다.")
    subparsers.add_parser("pending", help="승인 대기 중인 제안을 보여줍니다.")
    subparsers.add_parser("portfolio", help="시뮬레이션 계좌 현황을 보여줍니다.")
    subparsers.add_parser("monitor", help="조건 충족 시 매수 제안을 생성하는 감시 루프를 실행합니다.")
    subparsers.add_parser("telegram", help="텔레그램 버튼 UI 봇을 실행합니다.")
    approve_parser = subparsers.add_parser("approve", help="제안을 승인합니다.")
    approve_parser.add_argument("proposal_id", type=int)
    reject_parser = subparsers.add_parser("reject", help="제안을 거절합니다.")
    reject_parser.add_argument("proposal_id", type=int)

    args = parser.parse_args()
    settings = load_settings()
    storage = Storage(settings.db_path)
    client = create_broker_client(settings)

    if args.command == "init":
        storage.init()
        print(f"저장소를 준비했습니다: {settings.db_path}")
        print(f"브로커 모드: {settings.broker}")
        return

    storage.init()

    if args.command == "report":
        result = create_daily_report(storage, client, settings)
        print(render_daily_report(settings, result.signal, result.proposal_ids, result.recent_prices, result.monthly_plan))
        if result.chart_path:
            print("")
            print(f"차트: {result.chart_path}")
        else:
            print("")
            print("차트: matplotlib이 설치되어 있지 않아 생성하지 못했습니다.")
        return

    if args.command == "pending":
        proposals = storage.list_pending_proposals()
        if not proposals:
            print("승인 대기 중인 제안이 없습니다.")
            return
        for proposal in proposals:
            print(
                f"{proposal.id}. {proposal.name} {proposal.proposed_quantity:,}주 "
                f"({proposal.proposed_amount:,}원), {proposal.label}, 전술 {proposal.score}점"
            )
        return

    if args.command == "portfolio":
        account = storage.ensure_simulation_account(settings.simulation_initial_cash)
        positions = storage.list_simulation_positions()
        print("[시뮬레이션 계좌]")
        print(f"초기 현금: {account.initial_cash:,}원")
        print(f"현재 현금: {account.cash:,}원")
        if not positions:
            print("보유 종목이 없습니다.")
            return
        print("")
        for position in positions:
            print(
                f"{position.name} ({position.symbol}) "
                f"{position.quantity:,}주 / 평균단가 {position.avg_price:,.0f}원 / "
                f"투자원금 {position.invested_amount:,}원"
            )
        return

    if args.command == "approve":
        print(approve_proposal(storage, client, settings, args.proposal_id))
        return

    if args.command == "reject":
        print(reject_proposal(storage, args.proposal_id))
        return

    if args.command == "telegram":
        run_telegram_bot()
        return

    if args.command == "monitor":
        print("시장 감시를 시작합니다. 중지하려면 Ctrl+C를 누르세요.")
        while True:
            result = check_market_once(storage, client, settings)
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {result.reason}")
            if result.proposal_id:
                print(f"제안 생성: {result.proposal_id}")
            time.sleep(settings.monitor_interval_seconds)


if __name__ == "__main__":
    main()
