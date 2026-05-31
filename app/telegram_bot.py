from __future__ import annotations

import time
from typing import Any

from app.approval import approve_proposal, reject_proposal
from app.brokers import create_broker_client
from app.config import Settings, load_settings
from app.dca import load_monthly_plan, normalize_investment_settings
from app.models import InvestmentSettings
from app.monitor import check_market_once
from app.report_service import create_daily_report
from app.reporting import render_daily_report
from app.storage import Storage
from app.telegram_client import TelegramClient


def run_telegram_bot() -> None:
    settings = load_settings()
    storage = Storage(settings.db_path)
    storage.init()
    broker = create_broker_client(settings)
    telegram = TelegramClient(settings.telegram_bot_token)
    bot = TelegramBot(settings, storage, broker, telegram)
    bot.run()


class TelegramBot:
    def __init__(self, settings: Settings, storage: Storage, broker: Any, telegram: TelegramClient) -> None:
        self.settings = settings
        self.storage = storage
        self.broker = broker
        self.telegram = telegram
        self.offset: int | None = None
        self.last_monitor_at = 0.0

    def run(self) -> None:
        print("Telegram bot is running. Press Ctrl+C to stop.")
        while True:
            updates = self.telegram.get_updates(self.offset)
            for update in updates:
                self.offset = int(update["update_id"]) + 1
                try:
                    self.handle_update(update)
                except Exception as exc:
                    print(f"update handling failed: {exc}")
            self.maybe_run_monitor()

    def handle_update(self, update: dict[str, Any]) -> None:
        if "message" in update:
            self.handle_message(update["message"])
        elif "callback_query" in update:
            self.handle_callback(update["callback_query"])

    def handle_message(self, message: dict[str, Any]) -> None:
        chat_id = int(message["chat"]["id"])
        text = str(message.get("text", "")).strip()
        if not self.is_allowed(chat_id):
            self.handle_auth_attempt(chat_id, text)
            return
        if text in {"/start", "/menu", "menu", ""}:
            self.send_home(chat_id)
        elif text == "/report":
            self.send_report(chat_id)
        elif text == "/pending":
            self.send_pending(chat_id)
        elif text == "/status":
            self.send_status(chat_id)
        elif text == "/portfolio":
            self.send_portfolio(chat_id)
        elif text == "/settings":
            self.send_settings(chat_id)
        else:
            self.telegram.send_message(chat_id, "메뉴에서 원하는 작업을 선택해 주세요.", main_menu_keyboard())

    def handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback["id"])
        message = callback["message"]
        chat_id = int(message["chat"]["id"])
        message_id = int(message["message_id"])
        data = str(callback.get("data", ""))
        self.telegram.answer_callback_query(callback_id)

        if not self.is_allowed(chat_id):
            self.telegram.send_message(chat_id, auth_prompt_text())
            return
        if data == "menu":
            self.safe_edit_or_send(chat_id, message_id, home_text(self.settings, self.investment_settings()), main_menu_keyboard())
        elif data == "report":
            self.send_report(chat_id)
        elif data == "pending":
            self.send_pending(chat_id)
        elif data == "status":
            self.send_status(chat_id)
        elif data == "portfolio":
            self.send_portfolio(chat_id)
        elif data == "settings":
            self.safe_edit_or_send(
                chat_id,
                message_id,
                settings_text(self.investment_settings(), self.monitor_interval_seconds()),
                settings_keyboard(),
            )
        elif data.startswith("settings:"):
            text = self.apply_settings_callback(data)
            self.safe_edit_or_send(chat_id, message_id, text, settings_keyboard())
        elif data.startswith("approve:"):
            proposal_id = int(data.split(":", 1)[1])
            result = approve_proposal(self.storage, self.broker, self.settings, proposal_id)
            self.safe_edit_or_send(chat_id, message_id, result, main_menu_keyboard())
        elif data.startswith("reject:"):
            proposal_id = int(data.split(":", 1)[1])
            result = reject_proposal(self.storage, proposal_id)
            self.safe_edit_or_send(chat_id, message_id, result, main_menu_keyboard())
        else:
            self.telegram.send_message(chat_id, "알 수 없는 버튼입니다.", main_menu_keyboard())

    def safe_edit_or_send(self, chat_id: int, message_id: int, text: str, reply_markup: dict[str, Any]) -> None:
        if not self.telegram.try_edit_message_text(chat_id, message_id, text, reply_markup):
            self.telegram.send_message(chat_id, text, reply_markup)

    def investment_settings(self) -> InvestmentSettings:
        return self.storage.get_investment_settings(self.settings.default_investment_settings)

    def monitor_interval_seconds(self) -> int:
        return self.storage.get_int_setting("monitor_interval_seconds", self.settings.monitor_interval_seconds)

    def send_home(self, chat_id: int) -> None:
        self.telegram.send_message(chat_id, home_text(self.settings, self.investment_settings()), main_menu_keyboard())

    def send_report(self, chat_id: int) -> None:
        result = create_daily_report(self.storage, self.broker, self.settings)
        text = render_daily_report(
            self.settings,
            result.signal,
            result.proposal_ids,
            result.recent_prices,
            result.monthly_plan,
        )
        keyboard = proposal_keyboard(result.proposal_ids[0]) if len(result.proposal_ids) == 1 else main_menu_keyboard()
        self.telegram.send_message(chat_id, text, keyboard)
        if result.chart_path:
            self.telegram.send_photo(chat_id, result.chart_path, "가격 흐름과 이동평균입니다.", keyboard)

    def maybe_run_monitor(self) -> None:
        if not self.settings.monitor_enabled:
            return
        now = time.monotonic()
        if now - self.last_monitor_at < self.monitor_interval_seconds():
            return
        self.last_monitor_at = now
        result = check_market_once(self.storage, self.broker, self.settings)
        if not result.should_notify:
            print(f"monitor skipped: {result.reason}")
            return
        keyboard = proposal_keyboard(result.proposal_id)
        text = render_daily_report(self.settings, result.signal, result.proposal_id)
        alert_text = "[자동 매수 제안]\n\n" + text + f"\n\n사유: {result.reason}"
        for chat_id in self.notification_chat_ids():
            self.telegram.send_message(chat_id, alert_text, keyboard)
            if result.chart_path:
                self.telegram.send_photo(chat_id, result.chart_path, "자동 감시 차트입니다.", keyboard)

    def notification_chat_ids(self) -> list[int]:
        chat_ids = set(self.storage.list_telegram_authorized_chat_ids())
        if self.settings.telegram_allowed_chat_id is not None:
            chat_ids.add(self.settings.telegram_allowed_chat_id)
        return sorted(chat_ids)

    def send_pending(self, chat_id: int) -> None:
        proposals = self.storage.list_pending_proposals()
        if not proposals:
            self.telegram.send_message(chat_id, "승인 대기 중인 제안이 없습니다.", main_menu_keyboard())
            return
        self.telegram.send_message(chat_id, f"승인 대기 제안 {len(proposals)}건입니다.", main_menu_keyboard())
        for proposal in proposals:
            proposal_name = "기본 DCA" if proposal.proposal_type == "base_dca" else "전술 매수"
            text = (
                "[승인 대기]\n\n"
                f"번호: {proposal.id}\n"
                f"구분: {proposal_name}\n"
                f"월: {proposal.cycle_month or '-'}\n"
                f"종목: {proposal.name} ({proposal.symbol})\n"
                f"상태: {proposal.label}\n"
                f"전술 매력도: {proposal.score}점\n"
                f"제안 가격: {proposal.proposed_price:,}원\n"
                f"수량: {proposal.proposed_quantity:,}주\n"
                f"금액: {proposal.proposed_amount:,}원"
            )
            self.telegram.send_message(chat_id, text, proposal_keyboard(proposal.id))

    def send_status(self, chat_id: int) -> None:
        pending_count = len(self.storage.list_pending_proposals())
        investment = self.investment_settings()
        simulation_text = ""
        if self.settings.uses_simulation_account:
            account = self.storage.ensure_simulation_account(self.settings.simulation_initial_cash)
            positions = self.storage.list_simulation_positions()
            invested = sum(position.invested_amount for position in positions)
            simulation_text = (
                f"시뮬레이션 현금: {account.cash:,}원\n"
                f"시뮬레이션 투자원금: {invested:,}원\n"
                f"시뮬레이션 보유종목: {len(positions)}개\n"
            )
        plan_text = ""
        try:
            prices = self.broker.get_daily_prices(self.settings.etf_symbol)
            current_price = prices[-1].close
            plan = load_monthly_plan(self.storage, self.settings.default_investment_settings, current_price)
            plan_text = (
                f"이번 달 전술 집행: {plan.tactical_spent:,}원\n"
                f"이번 달 전술 잔액: {plan.tactical_remaining:,}원\n"
            )
            if plan.benchmark_summary:
                plan_text += f"{plan.benchmark_summary}\n"
        except Exception:
            plan_text = ""
        text = (
            "[시스템 상태]\n\n"
            f"시세 제공자: {self.settings.market_data_provider}\n"
            f"계좌 모드: {self.settings.account_provider}\n"
            f"종목: {self.settings.etf_name} ({self.settings.etf_symbol})\n"
            f"월 총액: {investment.total_budget:,}원\n"
            f"정기 매수일: 매월 {investment.dca_day}일\n"
            f"기본 DCA: {investment.base_budget:,}원\n"
            f"전술 자금: {investment.tactical_budget:,}원\n"
            f"{plan_text}"
            f"시뮬레이션 초기 현금: {self.settings.simulation_initial_cash:,}원\n"
            f"{simulation_text}"
            f"승인 대기: {pending_count}건\n"
            f"가격 재승인 기준: {self.settings.approval_max_price_drift_pct:.2f}%\n"
            f"일일 주문 상한: {self.settings.daily_max_order_amount:,}원\n\n"
            f"자동 감시: {'켜짐' if self.settings.monitor_enabled else '꺼짐'}\n"
            f"감시 주기: {self.monitor_interval_seconds() // 60}분\n"
            f"알림 기준 점수: {self.settings.monitor_min_score}점\n"
            f"중복 제안 대기: {self.settings.monitor_cooldown_minutes}분\n\n"
            "현재 버전은 주문을 바로 전송하지 않고 승인 기록과 시뮬레이션 체결을 저장합니다."
        )
        self.telegram.send_message(chat_id, text, main_menu_keyboard())

    def send_portfolio(self, chat_id: int) -> None:
        account = self.storage.ensure_simulation_account(self.settings.simulation_initial_cash)
        positions = self.storage.list_simulation_positions()
        lines = [
            "[시뮬레이션 계좌]",
            "",
            f"초기 현금: {account.initial_cash:,}원",
            f"현재 현금: {account.cash:,}원",
        ]
        if not positions:
            lines.append("보유 종목이 없습니다.")
        else:
            lines.append("")
            for position in positions:
                lines.extend(
                    [
                        f"{position.name} ({position.symbol})",
                        f"- 수량: {position.quantity:,}주",
                        f"- 평균단가: {position.avg_price:,.0f}원",
                        f"- 투자원금: {position.invested_amount:,}원",
                    ]
                )
        self.telegram.send_message(chat_id, "\n".join(lines), main_menu_keyboard())

    def send_settings(self, chat_id: int) -> None:
        self.telegram.send_message(chat_id, settings_text(self.investment_settings(), self.monitor_interval_seconds()), settings_keyboard())

    def apply_settings_callback(self, data: str) -> str:
        current = self.investment_settings()
        settings = current
        if data == "settings:preset:150_100_50":
            settings = InvestmentSettings(total_budget=1_500_000, base_budget=1_000_000, tactical_budget=500_000, dca_day=22)
        elif data.startswith("settings:day:"):
            day = int(data.rsplit(":", 1)[1])
            settings = InvestmentSettings(
                total_budget=current.total_budget,
                base_budget=current.base_budget,
                tactical_budget=current.tactical_budget,
                dca_day=day,
            )
        elif data.startswith("settings:split:"):
            base_ratio = int(data.rsplit(":", 1)[1])
            base_budget = current.total_budget * base_ratio // 100
            tactical_budget = current.total_budget - base_budget
            settings = InvestmentSettings(
                total_budget=current.total_budget,
                base_budget=base_budget,
                tactical_budget=tactical_budget,
                dca_day=current.dca_day,
            )
        elif data.startswith("settings:total:"):
            total_budget = int(data.rsplit(":", 1)[1])
            base_budget = min(current.base_budget, total_budget)
            tactical_budget = total_budget - base_budget
            settings = InvestmentSettings(
                total_budget=total_budget,
                base_budget=base_budget,
                tactical_budget=tactical_budget,
                dca_day=current.dca_day,
            )
        elif data.startswith("settings:monitor:"):
            minutes = int(data.rsplit(":", 1)[1])
            self.storage.set_int_setting("monitor_interval_seconds", minutes * 60)
            return "감시 주기를 저장했습니다.\n\n" + settings_text(current, minutes * 60)
        normalized = normalize_investment_settings(settings)
        self.storage.set_investment_settings(normalized)
        return "설정을 저장했습니다.\n\n" + settings_text(normalized, self.monitor_interval_seconds())

    def is_allowed(self, chat_id: int) -> bool:
        allowed = self.settings.telegram_allowed_chat_id
        if allowed is not None and chat_id == allowed:
            return True
        return self.storage.is_telegram_chat_authorized(chat_id)

    def handle_auth_attempt(self, chat_id: int, text: str) -> None:
        if text in {"/start", "/menu", "menu", ""}:
            self.telegram.send_message(chat_id, auth_prompt_text())
            return
        if not self.settings.telegram_auth_key:
            self.telegram.send_message(chat_id, "인증키가 설정되지 않았습니다. .env의 TELEGRAM_AUTH_KEY를 확인해 주세요.")
            return
        if text == self.settings.telegram_auth_key:
            self.storage.authorize_telegram_chat(chat_id)
            self.telegram.send_message(chat_id, "인증되었습니다. 이제 버튼으로 운영할 수 있습니다.", main_menu_keyboard())
            return
        self.telegram.send_message(chat_id, "인증키가 맞지 않습니다. 다시 입력해 주세요.")


def home_text(settings: Settings, investment: InvestmentSettings | None = None) -> str:
    investment_text = ""
    if investment:
        investment_text = (
            f"\n월 총액 {investment.total_budget:,}원 / "
            f"기본 {investment.base_budget:,}원 / 전술 {investment.tactical_budget:,}원\n"
            f"정기 매수일: 매월 {investment.dca_day}일"
        )
    return (
        "[ETF Dynamic DCA]\n\n"
        "기본 적립은 반드시 진행하고, 전술 자금은 월 안에서 더 나은 가격을 기다렸다가 제안합니다.\n"
        f"현재 시세 제공자는 {settings.market_data_provider}, 계좌 모드는 {settings.account_provider}입니다."
        f"{investment_text}\n\n"
        "실제 주문은 아직 전송하지 않고 승인 절차와 시뮬레이션 기록을 우선 사용합니다."
    )


def auth_prompt_text() -> str:
    return (
        "[인증 필요]\n\n"
        "개인 ETF 투자 보조 도구입니다.\n"
        "처음 사용하려면 인증키를 메시지로 보내주세요."
    )


def settings_text(settings: InvestmentSettings, monitor_interval_seconds: int | None = None) -> str:
    tactical_pct = settings.tactical_budget / settings.total_budget * 100 if settings.total_budget else 0
    base_pct = settings.base_budget / settings.total_budget * 100 if settings.total_budget else 0
    monitor_text = ""
    if monitor_interval_seconds is not None:
        monitor_text = f"감시 주기: {monitor_interval_seconds // 60}분\n"
    return (
        "[월간 투자 설정]\n\n"
        f"월 총액: {settings.total_budget:,}원\n"
        f"기본 DCA: {settings.base_budget:,}원 ({base_pct:.0f}%)\n"
        f"전술 자금: {settings.tactical_budget:,}원 ({tactical_pct:.0f}%)\n"
        f"정기 매수일: 매월 {settings.dca_day}일\n"
        f"{monitor_text}\n"
        "전술 자금은 좋은 구간을 기다리되, 월말에는 남은 금액을 소진하는 방향으로 제안합니다."
    )


def main_menu_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "일일 리포트", "callback_data": "report"},
                {"text": "승인 대기", "callback_data": "pending"},
            ],
            [
                {"text": "월간 설정", "callback_data": "settings"},
                {"text": "시스템 상태", "callback_data": "status"},
            ],
            [
                {"text": "시뮬 계좌", "callback_data": "portfolio"},
                {"text": "메뉴 새로고침", "callback_data": "menu"},
            ],
        ]
    }


def settings_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "150만 / 100만 / 50만", "callback_data": "settings:preset:150_100_50"}],
            [
                {"text": "정기일 15일", "callback_data": "settings:day:15"},
                {"text": "정기일 22일", "callback_data": "settings:day:22"},
                {"text": "정기일 25일", "callback_data": "settings:day:25"},
            ],
            [
                {"text": "기본 67%", "callback_data": "settings:split:67"},
                {"text": "기본 60%", "callback_data": "settings:split:60"},
                {"text": "기본 50%", "callback_data": "settings:split:50"},
            ],
            [
                {"text": "월 100만", "callback_data": "settings:total:1000000"},
                {"text": "월 150만", "callback_data": "settings:total:1500000"},
                {"text": "월 200만", "callback_data": "settings:total:2000000"},
            ],
            [
                {"text": "감시 15분", "callback_data": "settings:monitor:15"},
                {"text": "감시 30분", "callback_data": "settings:monitor:30"},
                {"text": "감시 60분", "callback_data": "settings:monitor:60"},
            ],
            [{"text": "메뉴", "callback_data": "menu"}],
        ]
    }


def proposal_keyboard(proposal_id: int | None) -> dict[str, Any]:
    if proposal_id is None:
        return main_menu_keyboard()
    return {
        "inline_keyboard": [
            [
                {"text": "승인", "callback_data": f"approve:{proposal_id}"},
                {"text": "거절", "callback_data": f"reject:{proposal_id}"},
            ],
            [
                {"text": "승인 대기 보기", "callback_data": "pending"},
                {"text": "메뉴", "callback_data": "menu"},
            ],
        ]
    }


if __name__ == "__main__":
    run_telegram_bot()
