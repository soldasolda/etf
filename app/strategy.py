from __future__ import annotations

from app.indicators import moving_average, return_pct, rsi, volume_change_ratio
from app.models import DailyPrice, Signal


def evaluate_signal(prices: list[DailyPrice], tactical_budget: int) -> Signal:
    if len(prices) < 60:
        raise ValueError("At least 60 daily prices are required to evaluate a signal.")

    current = prices[-1].close
    avg_3m = moving_average(prices, 60)
    avg_3w = moving_average(prices, 15)
    ma20 = moving_average(prices, 20)
    ma60 = moving_average(prices, 60)
    ma120 = moving_average(prices, 120)
    discount_pct = (current / avg_3m - 1.0) * 100
    recent_3w = prices[-15:]
    low_3w = min(item.close for item in recent_3w)
    high_3w = max(item.close for item in recent_3w)
    three_week_position_pct = ((current - low_3w) / (high_3w - low_3w) * 100) if high_3w != low_3w else 50.0
    pullback_from_3w_high_pct = (current / high_3w - 1.0) * 100 if high_3w else 0.0
    recent_120d = prices[-120:]
    low_120d = min(item.close for item in recent_120d)
    high_120d = max(item.close for item in recent_120d)
    range_position_120d_pct = ((current - low_120d) / (high_120d - low_120d) * 100) if high_120d != low_120d else 50.0
    pullback_from_120d_high_pct = (current / high_120d - 1.0) * 100 if high_120d else 0.0
    rsi14 = rsi(prices, 14)
    five_day_return = return_pct(prices, 5)
    volume_ratio = volume_change_ratio(prices)

    score = 0
    reasons: list[str] = []
    score_details: list[str] = []

    if discount_pct <= -7:
        score += 30
        score_details.append("가격 매력 +30: 3개월 평균 대비 -7% 이하")
        reasons.append("3개월 평균 대비 충분히 낮은 가격입니다.")
    elif discount_pct <= -5:
        score += 24
        score_details.append("가격 매력 +24: 3개월 평균 대비 -5% 이하")
        reasons.append("3개월 평균 대비 -5% 이하의 저가 구간입니다.")
    elif discount_pct <= -2:
        score += 14
        score_details.append("가격 매력 +14: 최근 평균보다 낮음")
        reasons.append("최근 평균보다 낮아 분할 매수 후보입니다.")
    elif discount_pct <= 3:
        score += 7
        score_details.append("가격 매력 +7: 3개월 평균 근처")
        reasons.append("평균가 근처라 무리한 추가 매수 근거는 약합니다.")
    else:
        score_details.append("가격 매력 +0: 3개월 평균보다 높음")
        reasons.append("3개월 평균보다 높아 전술 매수 매력은 낮습니다.")

    if ma20 > ma60:
        score += 20
        score_details.append("추세 +20: 20일선이 60일선 위")
        reasons.append("20일선이 60일선 위에 있어 상승 추세가 유지됩니다.")
    else:
        score += 6
        score_details.append("추세 +6: 20일선이 60일선 아래")
        reasons.append("20일선이 60일선 아래라 추세는 조심스럽습니다.")

    if current > ma120 and ma20 > ma60:
        score += 10
        score_details.append("장기 추세 +10: 현재가가 120일선 위이고 중기 추세도 양호")
        reasons.append("장기 추세가 살아 있어 눌림 매수 후보로 볼 수 있습니다.")
    elif current < ma120 and ma20 <= ma60:
        score -= 10
        score_details.append("장기 추세 -10: 현재가가 120일선 아래이고 중기 추세도 약함")
        reasons.append("가격이 싸 보여도 추세 훼손 위험이 있어 진입 강도를 낮춥니다.")

    if -6 <= five_day_return <= -2:
        score += 15
        score_details.append("단기 조정 +15: 최근 5거래일 -2%~-6%")
        reasons.append("최근 5거래일 조정이 있어 분할 진입 후보입니다.")
    elif five_day_return < -6:
        score += 5
        score_details.append("단기 조정 +5: 급락이라 진입 강도 축소")
        reasons.append("단기 급락 폭이 커서 추가 하락 위험을 봐야 합니다.")
    elif five_day_return > 4:
        score -= 6
        score_details.append("단기 조정 -6: 최근 5거래일 +4% 초과")
        reasons.append("단기 상승 폭이 커 추격 매수 위험이 있습니다.")
    else:
        score_details.append("단기 조정 +0: 뚜렷한 조정 없음")

    if volume_ratio >= 1.5 and five_day_return < -4:
        score -= 8
        score_details.append("거래량 -8: 거래량 증가 동반 급락")
        reasons.append("거래량 증가를 동반한 하락이라 급한 매수는 줄입니다.")
    elif volume_ratio >= 1.2:
        score += 4
        score_details.append("거래량 +4: 최근 거래량 증가")
        reasons.append("최근 거래량이 늘어 시장 관심이 높아졌습니다.")
    else:
        score_details.append("거래량 +0: 특이 변화 없음")

    if 35 <= rsi14 <= 55 and ma20 > ma60 and pullback_from_3w_high_pct <= -1:
        score += 10
        score_details.append(f"RSI/눌림 +10: RSI {rsi14:.0f}, 상승 추세 속 단기 눌림")
        reasons.append("RSI가 과열이 아니고 상승 추세 속 단기 눌림이 확인됩니다.")
    elif rsi14 >= 70:
        score -= 10
        score_details.append(f"RSI 과열 -10: RSI {rsi14:.0f}")
        reasons.append("RSI가 과열권이라 전술 자금 투입을 보수적으로 봅니다.")
    elif rsi14 <= 30 and current > ma120:
        score += 8
        score_details.append(f"RSI 저점 +8: RSI {rsi14:.0f}, 장기 추세 위의 과매도")
        reasons.append("장기 추세 위에서 RSI가 낮아 단기 과매도 후보입니다.")

    if pullback_from_120d_high_pct <= -7 and current > ma120:
        score += 12
        score_details.append("중기 눌림 +12: 120거래일 고점 대비 -7% 이하, 120일선 위")
        reasons.append("중기 고점 대비 충분한 눌림이지만 장기 추세는 유지됩니다.")
    elif range_position_120d_pct >= 90 and discount_pct > 5:
        score -= 8
        score_details.append("중기 상단 -8: 120거래일 범위 상단")
        reasons.append("최근 120거래일 범위 상단이라 가격 매력은 낮습니다.")

    if discount_pct > 5 and three_week_position_pct >= 80:
        score -= 8
        score_details.append("단기 과열 보정 -8: 3개월 평균보다 높고 최근 3주 상단")
        reasons.append("3개월 평균 대비 높고 최근 3주 범위 상단이라 추격 매수는 줄입니다.")
    elif pullback_from_3w_high_pct <= -3:
        score += 8
        score_details.append("단기 눌림 보정 +8: 최근 3주 고점 대비 -3% 이하")
        reasons.append("최근 3주 고점 대비 눌림이 있어 단기 가격 부담이 완화됐습니다.")

    score += 10
    score_details.append("기본 참여 +10: 장기 적립 투자 유지 점수")
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
        avg_3w=avg_3w,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        discount_pct=discount_pct,
        three_week_position_pct=three_week_position_pct,
        pullback_from_3w_high_pct=pullback_from_3w_high_pct,
        range_position_120d_pct=range_position_120d_pct,
        pullback_from_120d_high_pct=pullback_from_120d_high_pct,
        rsi14=rsi14,
        five_day_return_pct=five_day_return,
        reasons=reasons,
        score_details=score_details,
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
