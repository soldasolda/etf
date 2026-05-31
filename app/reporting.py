from __future__ import annotations

from app.config import Settings
from app.models import DailyPrice, Signal


def render_daily_report(
    settings: Settings,
    signal: Signal,
    proposal_id: int | None,
    recent_prices: list[DailyPrice] | None = None,
) -> str:
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
        f"20일선: {signal.ma20:,.0f}원",
        f"60일선: {signal.ma60:,.0f}원",
        f"최근 5거래일 수익률: {signal.five_day_return_pct:+.2f}%",
        f"점수: {signal.score}점",
        "",
        "[점수 구성]",
    ]
    lines.extend([f"- {detail}" for detail in signal.score_details])
    lines.extend(
        [
            "",
            "[점수 해석]",
            "- 점수는 매수 확률이 아니라 전술 자금을 써도 되는 정도입니다.",
            "- 3개월 평균은 장기 가격 부담을 보고, 최근 3주는 오늘 진입 위치를 보완합니다.",
            "- 과열 구간에서는 상승 추세여도 전술 자금 사용 비율을 낮춥니다.",
        ]
    )
    if recent_prices:
        lines.extend(["", "[최근 변동 가격표]"])
        lines.extend(render_recent_price_table(recent_prices))
    lines.extend(["", "[오늘의 판단]"])
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
                marker = "[빨강]△"
            elif change < 0:
                marker = "[파랑]▽"
            else:
                marker = "·"
            change_text = f"{marker}{change:+,}"
            rate_text = f"{marker}{rate:+.2f}%"
        rows.append(f"{item.trade_date:%m-%d}   {item.close:>8,}   {change_text:>10}   {rate_text:>10}")
        previous_close = item.close
    return rows
