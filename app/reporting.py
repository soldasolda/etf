from __future__ import annotations

from app.config import Settings
from app.models import Signal


def render_daily_report(settings: Settings, signal: Signal, proposal_id: int | None) -> str:
    lines = [
        "[ETF 일일 리포트]",
        "",
        f"종목: {settings.etf_name} ({settings.etf_symbol})",
        f"시장 상태: {signal.label}",
        f"현재가: {signal.current_price:,}원",
        f"3개월 평균: {signal.avg_3m:,.0f}원",
        f"3개월 평균 대비: {signal.discount_pct:+.2f}%",
        f"20일선: {signal.ma20:,.0f}원",
        f"60일선: {signal.ma60:,.0f}원",
        f"최근 5거래일 수익률: {signal.five_day_return_pct:+.2f}%",
        f"점수: {signal.score}점",
        "",
        "[오늘의 판단]",
    ]
    lines.extend([f"- {reason}" for reason in signal.reasons])
    lines.extend(
        [
            "",
            "[매수 제안]",
            f"전술 자금 사용 비율: {signal.buy_ratio * 100:.0f}%",
            f"추천 금액: {signal.tactical_amount:,}원",
            f"예상 수량: {signal.expected_quantity:,}주",
        ]
    )
    if proposal_id:
        lines.extend(
            [
                "",
                f"승인 대기 번호: {proposal_id}",
                f"승인: python -m app.main approve {proposal_id}",
                f"거절: python -m app.main reject {proposal_id}",
            ]
        )
    else:
        lines.extend(["", "오늘은 승인할 매수 제안이 없습니다."])
    return "\n".join(lines)
