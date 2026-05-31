from __future__ import annotations

from typing import Any

from app.approval import approve_proposal, reject_proposal
from app.brokers import create_broker_client
from app.config import Settings, load_settings
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

    def run(self) -> None:
        print("Telegram bot is running. Press Ctrl+C to stop.")
        while True:
            updates = self.telegram.get_updates(self.offset)
            for update in updates:
                self.offset = int(update["update_id"]) + 1
                self.handle_update(update)

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
            self.telegram.edit_message_text(chat_id, message_id, home_text(self.settings), main_menu_keyboard())
        elif data == "report":
            self.send_report(chat_id)
        elif data == "pending":
            self.send_pending(chat_id)
        elif data == "status":
            self.send_status(chat_id)
        elif data == "portfolio":
            self.send_portfolio(chat_id)
        elif data.startswith("approve:"):
            proposal_id = int(data.split(":", 1)[1])
            result = approve_proposal(self.storage, self.broker, self.settings, proposal_id)
            self.telegram.edit_message_text(chat_id, message_id, result, main_menu_keyboard())
        elif data.startswith("reject:"):
            proposal_id = int(data.split(":", 1)[1])
            result = reject_proposal(self.storage, proposal_id)
            self.telegram.edit_message_text(chat_id, message_id, result, main_menu_keyboard())
        else:
            self.telegram.send_message(chat_id, "알 수 없는 버튼입니다.", main_menu_keyboard())

    def send_home(self, chat_id: int) -> None:
        self.telegram.send_message(chat_id, home_text(self.settings), main_menu_keyboard())

    def send_report(self, chat_id: int) -> None:
        result = create_daily_report(self.storage, self.broker, self.settings)
        text = render_daily_report(self.settings, result.signal, result.proposal_id)
        keyboard = proposal_keyboard(result.proposal_id) if result.proposal_id else main_menu_keyboard()
        self.telegram.send_message(chat_id, text, keyboard)
        if result.chart_path:
            self.telegram.send_photo(chat_id, result.chart_path, "가격 흐름과 이동평균입니다.", keyboard)

    def send_pending(self, chat_id: int) -> None:
        proposals = self.storage.list_pending_proposals()
        if not proposals:
            self.telegram.send_message(chat_id, "승인 대기 중인 제안이 없습니다.", main_menu_keyboard())
            return
        self.telegram.send_message(chat_id, f"승인 대기 제안 {len(proposals)}건입니다.", main_menu_keyboard())
        for proposal in proposals:
            text = (
                "[승인 대기]\n\n"
                f"번호: {proposal.id}\n"
                f"종목: {proposal.name} ({proposal.symbol})\n"
                f"상태: {proposal.label}\n"
                f"점수: {proposal.score}점\n"
                f"제안 가격: {proposal.proposed_price:,}원\n"
                f"수량: {proposal.proposed_quantity:,}주\n"
                f"금액: {proposal.proposed_amount:,}원"
            )
            self.telegram.send_message(chat_id, text, proposal_keyboard(proposal.id))

    def send_status(self, chat_id: int) -> None:
        pending_count = len(self.storage.list_pending_proposals())
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
        text = (
            "[시스템 상태]\n\n"
            f"시세 제공자: {self.settings.market_data_provider}\n"
            f"계좌 모드: {self.settings.account_provider}\n"
            f"종목: {self.settings.etf_name} ({self.settings.etf_symbol})\n"
            f"기본 적립금: {self.settings.base_budget:,}원\n"
            f"전술 자금: {self.settings.tactical_budget:,}원\n"
            f"시뮬레이션 초기 현금: {self.settings.simulation_initial_cash:,}원\n"
            f"{simulation_text}"
            f"승인 대기: {pending_count}건\n"
            f"가격 재승인 기준: {self.settings.approval_max_price_drift_pct:.2f}%\n"
            f"일일 주문 상한: {self.settings.daily_max_order_amount:,}원\n\n"
            "현재 버전은 주문을 전송하지 않고 승인 기록만 저장합니다."
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


def home_text(settings: Settings) -> str:
    return (
        "[ETF DCA Assistant]\n\n"
        "버튼으로 일일 리포트와 승인 절차를 운영합니다.\n"
        f"현재 브로커는 {settings.broker}입니다.\n"
        f"계좌 모드는 {settings.account_provider}입니다.\n"
        "실제 주문은 아직 전송하지 않습니다."
    )


def auth_prompt_text() -> str:
    return (
        "[인증 필요]\n\n"
        "이 봇은 개인용 ETF 투자 보조 도구입니다.\n"
        "처음 사용하려면 인증키를 메시지로 보내주세요."
    )


def main_menu_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "일일 리포트", "callback_data": "report"},
                {"text": "승인 대기", "callback_data": "pending"},
            ],
            [
                {"text": "시스템 상태", "callback_data": "status"},
                {"text": "시뮬 계좌", "callback_data": "portfolio"},
            ],
            [
                {"text": "메뉴 새로고침", "callback_data": "menu"},
            ],
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
