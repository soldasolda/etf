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
    except ImportError:
        return None

    if not prices:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    dates = [item.trade_date for item in prices]
    closes = [item.close for item in prices]
    ma20 = rolling_average(closes, 20)
    ma60 = rolling_average(closes, 60)
    avg_3m = [signal.avg_3m for _ in closes]

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=140)
    ax.plot(dates, closes, color="#1f2937", linewidth=1.8, label="Close")
    ax.plot(dates, ma20, color="#2563eb", linewidth=1.2, label="MA20")
    ax.plot(dates, ma60, color="#f97316", linewidth=1.2, label="MA60")
    ax.plot(dates, avg_3m, color="#16a34a", linewidth=1.0, linestyle="--", label="3M Avg")
    ax.scatter([dates[-1]], [closes[-1]], color="#dc2626", s=42, zorder=5, label="Current")

    title = f"{name} ({symbol}) - {signal.label} / Score {signal.score}"
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


def rolling_average(values: list[int], window: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
        else:
            result.append(mean(values[index + 1 - window : index + 1]))
    return result
