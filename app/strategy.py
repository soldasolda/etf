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
    ma200 = moving_average(prices, 200)
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

    health_score, health_details = evaluate_health_score(current, ma20, ma60, ma120, ma200)
    tactical_score, tactical_details, reasons = evaluate_tactical_score(
        discount_pct=discount_pct,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        current=current,
        rsi14=rsi14,
        five_day_return=five_day_return,
        volume_ratio=volume_ratio,
        range_position_120d_pct=range_position_120d_pct,
        pullback_from_120d_high_pct=pullback_from_120d_high_pct,
        three_week_position_pct=three_week_position_pct,
        pullback_from_3w_high_pct=pullback_from_3w_high_pct,
    )

    health_label = classify_health(health_score)
    tactical_label = classify_tactical(tactical_score, health_score, discount_pct, five_day_return, volume_ratio)
    label = classify_market(health_score, tactical_score, ma20, ma60, discount_pct, five_day_return, volume_ratio)
    buy_ratio = calculate_buy_ratio(tactical_score, tactical_label)
    amount = int(tactical_budget * buy_ratio)
    quantity = amount // current if current > 0 else 0

    score_details = [
        f"건강도 {health_score}점: {health_label}",
        f"전술 매력도 {tactical_score}점: {tactical_label}",
    ]
    score_details.extend(tactical_details)

    return Signal(
        score=tactical_score,
        label=label,
        health_score=health_score,
        health_label=health_label,
        tactical_score=tactical_score,
        tactical_label=tactical_label,
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
        health_details=health_details,
        tactical_details=tactical_details,
    )


def evaluate_health_score(current: int, ma20: float, ma60: float, ma120: float, ma200: float) -> tuple[int, list[str]]:
    score = 0
    details: list[str] = []
    if current > ma120:
        score += 25
        details.append("현재가가 120일선 위에 있어 장기 추세가 유지됩니다.")
    else:
        details.append("현재가가 120일선 아래라 장기 추세 확인이 필요합니다.")

    if current > ma200:
        score += 25
        details.append("현재가가 200일선 위에 있어 장기 투자 건강도가 높습니다.")
    else:
        details.append("현재가가 200일선 아래라 장기 투자 건강도를 낮춥니다.")

    if ma20 > ma60 > ma120:
        score += 30
        details.append("20/60/120일선이 정배열입니다.")
    elif ma20 > ma60:
        score += 18
        details.append("20일선이 60일선 위라 중기 상승 흐름은 살아 있습니다.")
    elif ma60 > ma120:
        score += 8
        details.append("단기 정배열은 아니지만 60일선이 120일선 위입니다.")
    else:
        details.append("이동평균 정배열이 아닙니다.")

    if ma120 > ma200:
        score += 20
        details.append("120일선이 200일선 위라 장기 구조가 양호합니다.")
    elif ma60 > ma120:
        score += 10
        details.append("장기 정배열 전환 전이지만 중기 구조는 양호합니다.")
    else:
        details.append("120일선과 200일선 구조는 아직 보수적으로 봅니다.")

    return max(0, min(100, score)), details


def evaluate_tactical_score(
    *,
    discount_pct: float,
    ma20: float,
    ma60: float,
    ma120: float,
    current: int,
    rsi14: float,
    five_day_return: float,
    volume_ratio: float,
    range_position_120d_pct: float,
    pullback_from_120d_high_pct: float,
    three_week_position_pct: float,
    pullback_from_3w_high_pct: float,
) -> tuple[int, list[str], list[str]]:
    score = 0
    details: list[str] = []
    reasons: list[str] = []

    if discount_pct <= -7:
        score += 30
        details.append("가격 매력 +30: 3개월 평균 대비 -7% 이하")
        reasons.append("3개월 평균 대비 충분히 낮은 가격입니다.")
    elif discount_pct <= -5:
        score += 24
        details.append("가격 매력 +24: 3개월 평균 대비 -5% 이하")
        reasons.append("3개월 평균 대비 -5% 이하의 저가 구간입니다.")
    elif discount_pct <= -2:
        score += 14
        details.append("가격 매력 +14: 최근 평균보다 낮음")
        reasons.append("최근 평균보다 낮아 분할 매수 후보입니다.")
    elif discount_pct <= 3:
        score += 7
        details.append("가격 매력 +7: 3개월 평균 근처")
        reasons.append("평균가 근처라 무리한 추가 매수 근거는 약합니다.")
    else:
        details.append("가격 매력 +0: 3개월 평균보다 높음")
        reasons.append("3개월 평균보다 높아 전술 매수 매력은 낮습니다.")

    if -6 <= five_day_return <= -2:
        score += 18
        details.append("단기 조정 +18: 최근 5거래일 -2%~-6%")
        reasons.append("최근 5거래일 조정이 있어 전술 분할 진입 후보입니다.")
    elif five_day_return < -6:
        score += 6
        details.append("단기 조정 +6: 급락이라 진입 강도 축소")
        reasons.append("단기 급락 폭이 커서 추가 하락 위험을 봐야 합니다.")
    elif five_day_return > 4:
        score -= 8
        details.append("단기 상승 -8: 최근 5거래일 +4% 초과")
        reasons.append("단기 상승 폭이 커 추격 매수 위험이 있습니다.")
    else:
        details.append("단기 조정 +0: 뚜렷한 조정 없음")

    if 35 <= rsi14 <= 55 and ma20 > ma60 and pullback_from_3w_high_pct <= -1:
        score += 16
        details.append(f"RSI/눌림 +16: RSI {rsi14:.0f}, 상승 추세 속 단기 눌림")
        reasons.append("RSI가 과열이 아니고 상승 추세 속 단기 눌림이 확인됩니다.")
    elif rsi14 >= 70:
        score -= 10
        details.append(f"RSI 과열 -10: RSI {rsi14:.0f}")
        reasons.append("RSI가 과열권이라 전술 자금 투입을 보수적으로 봅니다.")
    elif rsi14 <= 30 and current > ma120:
        score += 12
        details.append(f"RSI 저점 +12: RSI {rsi14:.0f}, 장기 추세 위의 과매도")
        reasons.append("장기 추세 위에서 RSI가 낮아 단기 과매도 후보입니다.")
    else:
        details.append(f"RSI +0: RSI {rsi14:.0f}")

    if pullback_from_120d_high_pct <= -7 and current > ma120:
        score += 18
        details.append("중기 눌림 +18: 120거래일 고점 대비 -7% 이하, 120일선 위")
        reasons.append("중기 고점 대비 충분한 눌림이지만 장기 추세는 유지됩니다.")
    elif pullback_from_120d_high_pct <= -3 and current > ma120:
        score += 10
        details.append("중기 눌림 +10: 120거래일 고점 대비 -3% 이하, 120일선 위")
        reasons.append("중기 고점 대비 부담이 일부 완화됐습니다.")
    elif range_position_120d_pct >= 90 and discount_pct > 5:
        score -= 8
        details.append("중기 상단 -8: 120거래일 범위 상단")
        reasons.append("최근 120거래일 범위 상단이라 가격 매력은 낮습니다.")

    if discount_pct > 5 and three_week_position_pct >= 80:
        score -= 8
        details.append("단기 과열 보정 -8: 3개월 평균보다 높고 최근 3주 상단")
        reasons.append("3개월 평균 대비 높고 최근 3주 범위 상단이라 추격 매수는 줄입니다.")
    elif pullback_from_3w_high_pct <= -3:
        score += 10
        details.append("단기 눌림 보정 +10: 최근 3주 고점 대비 -3% 이하")
        reasons.append("최근 3주 고점 대비 눌림이 있어 단기 가격 부담이 완화됐습니다.")

    if volume_ratio >= 1.5 and five_day_return < -4:
        score -= 8
        details.append("거래량 -8: 거래량 증가 동반 급락")
        reasons.append("거래량 증가를 동반한 하락이라 급한 매수는 줄입니다.")
    elif volume_ratio >= 1.2:
        score += 4
        details.append("거래량 +4: 최근 거래량 증가")
        reasons.append("최근 거래량이 늘어 시장 관심이 높아졌습니다.")
    else:
        details.append("거래량 +0: 특이 변화 없음")

    return max(0, min(100, score)), details, reasons


def classify_health(score: int) -> str:
    if score >= 85:
        return "장기 투자 적합"
    if score >= 65:
        return "장기 추세 양호"
    if score >= 45:
        return "중립"
    return "추세 점검 필요"


def classify_tactical(score: int, health_score: int, discount_pct: float, five_day_return: float, volume_ratio: float) -> str:
    if five_day_return < -6 and volume_ratio >= 1.5:
        return "공포 구간"
    if score >= 75:
        return "전술 적극 구간"
    if score >= 55:
        return "전술 매수 구간"
    if score >= 35:
        return "소액 참여 구간"
    if health_score >= 75 and discount_pct > 5:
        return "단기 과열"
    return "전술 보류 구간"


def classify_market(
    health_score: int,
    tactical_score: int,
    ma20: float,
    ma60: float,
    discount_pct: float,
    five_day_return: float,
    volume_ratio: float,
) -> str:
    tactical_label = classify_tactical(tactical_score, health_score, discount_pct, five_day_return, volume_ratio)
    if tactical_label in {"공포 구간", "전술 적극 구간", "전술 매수 구간"}:
        return tactical_label
    if ma20 > ma60 and discount_pct <= -3:
        return "상승 추세 중 단기 조정"
    if health_score >= 85 and tactical_label == "단기 과열":
        return "장기 우상향 / 단기 과열"
    if ma20 > ma60:
        return "상승 추세"
    if health_score < 45:
        return "관망 구간"
    return "횡보 구간"


def calculate_buy_ratio(score: int, label: str) -> float:
    if label == "공포 구간":
        return 0.2 if score >= 50 else 0.0
    if label == "단기 과열":
        return 0.0
    if score >= 85:
        return 0.8
    if score >= 75:
        return 0.6
    if score >= 55:
        return 0.4
    if score >= 35:
        return 0.2
    return 0.0
