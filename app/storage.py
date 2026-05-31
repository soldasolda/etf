from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.models import DailyPrice, Proposal, Signal


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists price_daily (
                    symbol text not null,
                    trade_date text not null,
                    open integer not null,
                    high integer not null,
                    low integer not null,
                    close integer not null,
                    volume integer not null,
                    primary key (symbol, trade_date)
                );

                create table if not exists signal_daily (
                    id integer primary key autoincrement,
                    symbol text not null,
                    signal_date text not null,
                    score integer not null,
                    label text not null,
                    buy_ratio real not null,
                    current_price integer not null,
                    avg_3m real not null,
                    ma20 real not null,
                    ma60 real not null,
                    discount_pct real not null,
                    five_day_return_pct real not null,
                    reasons text not null,
                    created_at text not null
                );

                create table if not exists proposals (
                    id integer primary key autoincrement,
                    symbol text not null,
                    name text not null,
                    status text not null,
                    proposed_price integer not null,
                    proposed_amount integer not null,
                    proposed_quantity integer not null,
                    score integer not null,
                    label text not null,
                    created_at text not null,
                    decided_at text,
                    decision_note text
                );

                create table if not exists telegram_authorized_chats (
                    chat_id integer primary key,
                    authorized_at text not null
                );
                """
            )

    def upsert_prices(self, symbol: str, prices: list[DailyPrice]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                insert into price_daily
                    (symbol, trade_date, open, high, low, close, volume)
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(symbol, trade_date) do update set
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume
                """,
                [
                    (
                        symbol,
                        item.trade_date.isoformat(),
                        item.open,
                        item.high,
                        item.low,
                        item.close,
                        item.volume,
                    )
                    for item in prices
                ],
            )

    def get_prices(self, symbol: str, limit: int = 120) -> list[DailyPrice]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select trade_date, open, high, low, close, volume
                from price_daily
                where symbol = ?
                order by trade_date desc
                limit ?
                """,
                (symbol, limit),
            ).fetchall()
        prices = [
            DailyPrice(
                trade_date=date.fromisoformat(row["trade_date"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in reversed(rows)
        ]
        return prices

    def save_signal(self, symbol: str, signal: Signal) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into signal_daily
                    (symbol, signal_date, score, label, buy_ratio, current_price,
                     avg_3m, ma20, ma60, discount_pct, five_day_return_pct,
                     reasons, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    date.today().isoformat(),
                    signal.score,
                    signal.label,
                    signal.buy_ratio,
                    signal.current_price,
                    signal.avg_3m,
                    signal.ma20,
                    signal.ma60,
                    signal.discount_pct,
                    signal.five_day_return_pct,
                    "\n".join(signal.reasons),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def create_proposal(self, symbol: str, name: str, signal: Signal) -> int | None:
        if signal.expected_quantity <= 0 or signal.tactical_amount <= 0:
            return None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into proposals
                    (symbol, name, status, proposed_price, proposed_amount,
                     proposed_quantity, score, label, created_at)
                values (?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    name,
                    signal.current_price,
                    signal.tactical_amount,
                    signal.expected_quantity,
                    signal.score,
                    signal.label,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def list_pending_proposals(self) -> list[Proposal]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select id, symbol, name, created_at, status, proposed_price,
                       proposed_amount, proposed_quantity, score, label
                from proposals
                where status = 'pending'
                order by id
                """
            ).fetchall()
        return [_proposal_from_row(row) for row in rows]

    def get_proposal(self, proposal_id: int) -> Proposal | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select id, symbol, name, created_at, status, proposed_price,
                       proposed_amount, proposed_quantity, score, label
                from proposals
                where id = ?
                """,
                (proposal_id,),
            ).fetchone()
        return _proposal_from_row(row) if row else None

    def decide_proposal(self, proposal_id: int, status: str, note: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                update proposals
                set status = ?, decided_at = ?, decision_note = ?
                where id = ?
                """,
                (status, datetime.now().isoformat(timespec="seconds"), note, proposal_id),
            )

    def is_telegram_chat_authorized(self, chat_id: int) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "select chat_id from telegram_authorized_chats where chat_id = ?",
                (chat_id,),
            ).fetchone()
        return row is not None

    def authorize_telegram_chat(self, chat_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                insert into telegram_authorized_chats (chat_id, authorized_at)
                values (?, ?)
                on conflict(chat_id) do update set
                    authorized_at=excluded.authorized_at
                """,
                (chat_id, datetime.now().isoformat(timespec="seconds")),
            )


def _proposal_from_row(row: sqlite3.Row) -> Proposal:
    return Proposal(
        id=row["id"],
        symbol=row["symbol"],
        name=row["name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        status=row["status"],
        proposed_price=row["proposed_price"],
        proposed_amount=row["proposed_amount"],
        proposed_quantity=row["proposed_quantity"],
        score=row["score"],
        label=row["label"],
    )
