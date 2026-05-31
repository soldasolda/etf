from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import mean

from app.models import DailyPrice, Signal


def create_price_chart(
    prices: list[DailyPrice],
    signal: Signal,
    symbol: str,
    name: str,
    output_dir: Path,
) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError:
        return None

    configure_korean_font(plt, font_manager)

    if not prices:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    full_dates = [item.trade_date for item in prices]
    full_closes = [item.close for item in prices]
    full_ma20 = rolling_average(full_closes, 20)
    full_ma60 = rolling_average(full_closes, 60)

    window = min(15, len(prices))
    dates = full_dates[-window:]
    closes = full_closes[-window:]
    ma20 = full_ma20[-window:]
    ma60 = full_ma60[-window:]
    avg_3m = [signal.avg_3m for _ in closes]
    avg_3w = [signal.avg_3w for _ in closes]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=140)
    plot_candles(ax, prices[-window:])
    ax.plot(dates, closes, color="#111827", linewidth=1.0, alpha=0.55, label="Close")
    ax.plot(dates, ma20, color="#2563eb", linewidth=1.2, label="MA20")
    ax.plot(dates, ma60, color="#f97316", linewidth=1.2, label="MA60")
    ax.plot(dates, avg_3m, color="#16a34a", linewidth=1.0, linestyle="--", label="3M Avg")
    ax.plot(dates, avg_3w, color="#7c3aed", linewidth=1.0, linestyle=":", label="3W Avg")
    ax.scatter([dates[-1]], [closes[-1]], color="#dc2626", s=42, zorder=5, label="Current")

    title = (
        f"{name} ({symbol}) - 최근 3주 / "
        f"건강 {signal.health_score} / 전술 {signal.tactical_score}"
    )
    ax.set_title(title, fontsize=12, pad=12)
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.22)
    ax.legend(loc="upper left", ncol=5, fontsize=8, frameon=False)

    current_text = (
        f"Current {signal.current_price:,}\n"
        f"3M {signal.discount_pct:+.2f}%\n"
        f"Buy {signal.buy_ratio * 100:.0f}%"
    )
    ax.annotate(
        current_text,
        xy=(dates[-1], closes[-1]),
        xytext=(-88, 42),
        textcoords="offset points",
        fontsize=8,
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#d1d5db"},
        arrowprops={"arrowstyle": "->", "color": "#6b7280", "lw": 0.8},
    )

    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    path = output_dir / f"{symbol}_{date.today().isoformat()}_report.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_candles(ax, prices: list[DailyPrice]) -> None:
    for item in prices:
        up = item.close >= item.open
        color = "#dc2626" if up else "#2563eb"
        lower = min(item.open, item.close)
        height = abs(item.close - item.open) or 1
        ax.vlines(item.trade_date, item.low, item.high, color=color, linewidth=1.1, alpha=0.8)
        ax.bar(item.trade_date, height, bottom=lower, width=0.58, color=color, edgecolor=color, alpha=0.28)


def rolling_average(values: list[int], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
        else:
            result.append(mean(values[index + 1 - window : index + 1]))
    return result


def configure_korean_font(plt, font_manager) -> None:
    candidates = [
        "Malgun Gothic",
        "맑은 고딕",
        "AppleGothic",
        "NanumGothic",
        "Noto Sans CJK KR",
        "Noto Sans KR",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in candidates:
        if candidate in available:
            plt.rcParams["font.family"] = candidate
            plt.rcParams["axes.unicode_minus"] = False
            return
    plt.rcParams["axes.unicode_minus"] = False
