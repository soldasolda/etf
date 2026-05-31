from __future__ import annotations

from app.config import Settings
from app.dca import MonthlyPlan, decide_tactical_buy
from app.models import DailyPrice, Signal


def render_daily_report(
    settings: Settings,
    signal: Signal,
    proposal_ids: list[int] | int | None,
    recent_prices: list[DailyPrice] | None = None,
    monthly_plan: MonthlyPlan | None = None,
) -> str:
    if isinstance(proposal_ids, int):
        normalized_proposal_ids = [proposal_ids]
    else:
        normalized_proposal_ids = proposal_ids or []
    lines = [
        "[ETF 일일 리포트]",
        "",
        f"종목: {settings.etf_name} ({settings.etf_symbol})",
        f"시장 상태: {signal.label}",
        f"현재가: {signal.current_price:,}원",
        f"3개월 평균: {signal.avg_3m:,.0f}원",
        f"3개월 평균 대비: {signal.discount_pct:+.2f}%",
        f"3주 평균: {signal.avg_3w:,.0f}원",
        f"최근 3주 위치: 하단 0 / 상단 100 기준 {signal.three_week_position_pct:.0f}",
        f"최근 3주 고점 대비: {signal.pullback_from_3w_high_pct:+.2f}%",
        f"120거래일 위치: 하단 0 / 상단 100 기준 {signal.range_position_120d_pct:.0f}",
        f"120거래일 고점 대비: {signal.pullback_from_120d_high_pct:+.2f}%",
        f"RSI(14): {signal.rsi14:.0f}",
        f"20일선: {signal.ma20:,.0f}원",
        f"60일선: {signal.ma60:,.0f}원",
        f"120일선: {signal.ma120:,.0f}원",
        f"최근 5거래일 수익률: {signal.five_day_return_pct:+.2f}%",
        f"ETF 건강도: {signal.health_score}점 / {signal.health_label}",
        f"전술 매수 매력도: {signal.tactical_score}점 / {signal.tactical_label}",
        "",
        "[건강도 사유]",
    ]
    lines.extend([f"- {detail}" for detail in signal.health_details])
    lines.extend(["", "[전술 매력도 사유]"])
    lines.extend([f"- {detail}" for detail in signal.tactical_details])
    lines.extend(
        [
            "",
            "[점수 의미]",
            "- ETF 건강도는 장기 적립을 계속할 만한 추세 품질입니다.",
            "- 전술 매수 매력도는 지금 추가 자금을 더 넣기 좋은 가격인지 봅니다.",
            "- 최종 제안 금액은 전술 매력도에 DCA 원칙, 월말 소진, 건강도를 함께 반영합니다.",
        ]
    )
    if recent_prices:
        lines.extend(["", "[최근 변동 가격표]"])
        lines.extend(render_recent_price_table(recent_prices))
    lines.extend(["", "[오늘의 판단]"])
    lines.extend([f"- {reason}" for reason in signal.reasons])
    if monthly_plan:
        tactical_decision = decide_tactical_buy(signal, monthly_plan, settings.monitor_min_score)
        lines.extend(
            [
                "",
                "[월간 집행 계획]",
                f"정기 매수일: 매월 {monthly_plan.settings.dca_day}일",
                f"월 총액: {monthly_plan.settings.total_budget:,}원",
                f"기본 DCA: {monthly_plan.settings.base_budget:,}원",
                f"전술 자금: {monthly_plan.settings.tactical_budget:,}원",
                f"이번 달 전술 집행: {monthly_plan.tactical_spent:,}원",
                f"이번 달 전술 잔액: {monthly_plan.tactical_remaining:,}원",
            ]
        )
        if monthly_plan.benchmark_summary:
            lines.extend(["", "[벤치마크]", monthly_plan.benchmark_summary])
    else:
        tactical_decision = None
    proposal_ratio = tactical_decision.ratio if tactical_decision else signal.buy_ratio
    proposal_amount = tactical_decision.amount if tactical_decision else signal.tactical_amount
    proposal_quantity = tactical_decision.quantity if tactical_decision else signal.expected_quantity
    lines.extend(
        [
            "",
            "[매수 제안]",
            f"전술 자금 사용 비율: {proposal_ratio * 100:.0f}%",
            f"추천 금액: {proposal_amount:,}원",
            f"예상 수량: {proposal_quantity:,}주",
        ]
    )
    if tactical_decision and tactical_decision.reasons:
        lines.extend(["", "[DCA 적용 사유]"])
        lines.extend([f"- {reason}" for reason in tactical_decision.reasons])
    if normalized_proposal_ids:
        proposal_text = ", ".join(str(item) for item in normalized_proposal_ids)
        lines.extend(
            [
                "",
                f"승인 대기 번호: {proposal_text}",
                "텔레그램의 승인 대기 메뉴에서 각 제안을 승인/거절하세요.",
            ]
        )
    else:
        if proposal_amount > 0:
            lines.extend(["", "매수 후보 금액은 있지만 최근 제안/승인 대기 또는 중복 방지 조건으로 새 승인번호는 생성되지 않았습니다."])
        else:
            lines.extend(["", "오늘은 승인할 매수 제안이 없습니다."])
    return "\n".join(lines)


def render_recent_price_table(prices: list[DailyPrice]) -> list[str]:
    rows = ["날짜        종가        전일비      등락률"]
    previous_close: int | None = None
    for item in prices:
        if previous_close is None:
            change_text = "-"
            rate_text = "-"
        else:
            change = item.close - previous_close
            rate = (change / previous_close * 100) if previous_close else 0
            if change > 0:
                marker = "△"
            elif change < 0:
                marker = "▽"
            else:
                marker = "·"
            change_text = f"{marker}{change:+,}"
            rate_text = f"{marker}{rate:+.2f}%"
        rows.append(f"{item.trade_date:%m-%d}   {item.close:>8,}   {change_text:>10}   {rate_text:>10}")
        previous_close = item.close
    return rows
