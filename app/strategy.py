from __future__ import annotations

from app.indicators import moving_average, return_pct, volume_change_ratio
from app.models import DailyPrice, Signal


def evaluate_signal(prices: list[DailyPrice], tactical_budget: int) -> Signal:
    if len(prices) < 60:
        raise ValueError("At least 60 daily prices are required to evaluate a signal.")

    current = prices[-1].close
    avg_3m = moving_average(prices, 60)
    ma20 = moving_average(prices, 20)
    ma60 = moving_average(prices, 60)
    discount_pct = (current / avg_3m - 1.0) * 100
    five_day_return = return_pct(prices, 5)
    volume_ratio = volume_change_ratio(prices)

    score = 0
    reasons: list[str] = []

    if discount_pct <= -7:
        score += 30
        reasons.append("3개월 평균 대비 충분히 낮은 가격입니다.")
    elif discount_pct <= -5:
        score += 24
        reasons.append("3개월 평균 대비 -5% 이하의 저가 구간입니다.")
    elif discount_pct <= -2:
        score += 14
        reasons.append("최근 평균보다 낮아 분할 매수 후보입니다.")
    elif discount_pct <= 3:
        score += 7
        reasons.append("평균가 근처라 무리한 추가 매수 근거는 약합니다.")
    else:
        reasons.append("3개월 평균보다 높아 전술 매수 매력은 낮습니다.")

    if ma20 > ma60:
        score += 20
        reasons.append("20일선이 60일선 위에 있어 상승 추세가 유지됩니다.")
    else:
        score += 6
        reasons.append("20일선이 60일선 아래라 추세는 조심스럽습니다.")

    if -6 <= five_day_return <= -2:
        score += 15
        reasons.append("최근 5거래일 조정이 있어 분할 진입 후보입니다.")
    elif five_day_return < -6:
        score += 5
        reasons.append("단기 급락 폭이 커서 추가 하락 위험을 봐야 합니다.")
    elif five_day_return > 4:
        score -= 6
        reasons.append("단기 상승 폭이 커 추격 매수 위험이 있습니다.")

    if volume_ratio >= 1.5 and five_day_return < -4:
        score -= 8
        reasons.append("거래량 증가를 동반한 하락이라 급한 매수는 줄입니다.")
    elif volume_ratio >= 1.2:
        score += 4
        reasons.append("최근 거래량이 늘어 시장 관심이 높아졌습니다.")

    score += 10
    score = max(0, min(100, score))

    label = classify_market(score, ma20, ma60, discount_pct, five_day_return, volume_ratio)
    buy_ratio = calculate_buy_ratio(score, label)
    amount = int(tactical_budget * buy_ratio)
    quantity = amount // current if current > 0 else 0

    return Signal(
        score=score,
        label=label,
        buy_ratio=buy_ratio,
        tactical_amount=quantity * current,
        expected_quantity=quantity,
        current_price=current,
        avg_3m=avg_3m,
        ma20=ma20,
        ma60=ma60,
        discount_pct=discount_pct,
        five_day_return_pct=five_day_return,
        reasons=reasons,
    )


def classify_market(
    score: int,
    ma20: float,
    ma60: float,
    discount_pct: float,
    five_day_return: float,
    volume_ratio: float,
) -> str:
    if discount_pct > 7 and five_day_return > 3:
        return "과열 구간"
    if five_day_return < -6 and volume_ratio >= 1.5:
        return "공포 구간"
    if ma20 > ma60 and discount_pct <= -3:
        return "상승 추세 중 단기 조정"
    if discount_pct <= -5:
        return "저가 매수 구간"
    if ma20 > ma60:
        return "상승 추세"
    if score < 40:
        return "관망 구간"
    return "횡보 구간"


def calculate_buy_ratio(score: int, label: str) -> float:
    if label == "공포 구간":
        return 0.2 if score >= 50 else 0.0
    if label == "과열 구간":
        return 0.0
    if score >= 85:
        return 0.8
    if score >= 75:
        return 0.6
    if score >= 60:
        return 0.4
    if score >= 40:
        return 0.2
    return 0.0
