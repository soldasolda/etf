from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "etf.sqlite3"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    broker: str
    market_data_provider: str
    account_provider: str
    appkey: str
    secretkey: str
    mock: bool
    telegram_bot_token: str
    telegram_allowed_chat_id: int | None
    telegram_auth_key: str
    etf_symbol: str
    etf_name: str
    base_budget: int
    tactical_budget: int
    simulation_initial_cash: int
    cycle_day: int
    holiday_policy: str
    approval_max_price_drift_pct: float
    daily_max_order_amount: int
    db_path: Path

    @property
    def has_api_credentials(self) -> bool:
        return bool(self.appkey and self.secretkey)

    @property
    def uses_simulation_account(self) -> bool:
        return self.account_provider == "simulation"


def load_settings() -> Settings:
    _load_dotenv(ROOT_DIR / ".env")
    allowed_chat_id = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    legacy_broker = os.getenv("BROKER", "").lower().strip()
    market_data_provider = os.getenv("MARKET_DATA_PROVIDER", legacy_broker or "fdr").lower()
    account_provider = os.getenv("ACCOUNT_PROVIDER", _default_account_provider(market_data_provider)).lower()
    return Settings(
        broker=market_data_provider,
        market_data_provider=market_data_provider,
        account_provider=account_provider,
        appkey=os.getenv("TOSS_APPKEY", ""),
        secretkey=os.getenv("TOSS_SECRETKEY", ""),
        mock=_bool_env("TOSS_MOCK", True),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_allowed_chat_id=int(allowed_chat_id) if allowed_chat_id else None,
        telegram_auth_key=os.getenv("TELEGRAM_AUTH_KEY", ""),
        etf_symbol=os.getenv("ETF_SYMBOL", "360750"),
        etf_name=os.getenv("ETF_NAME", "TIGER 미국S&P500"),
        base_budget=int(os.getenv("BASE_BUDGET", "1000000")),
        tactical_budget=int(os.getenv("TACTICAL_BUDGET", "500000")),
        simulation_initial_cash=int(os.getenv("SIMULATION_INITIAL_CASH", "5000000")),
        cycle_day=int(os.getenv("CYCLE_DAY", "21")),
        holiday_policy=os.getenv("HOLIDAY_POLICY", "next_business_day"),
        approval_max_price_drift_pct=float(os.getenv("APPROVAL_MAX_PRICE_DRIFT_PCT", "0.3")),
        daily_max_order_amount=int(os.getenv("DAILY_MAX_ORDER_AMOUNT", "300000")),
        db_path=DB_PATH,
    )


def _default_account_provider(market_data_provider: str) -> str:
    if market_data_provider in {"sample", "fdr"}:
        return "simulation"
    if market_data_provider == "toss":
        return "api"
    return "simulation"
