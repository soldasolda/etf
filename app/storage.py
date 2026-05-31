from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.models import DailyPrice, Proposal, Signal, SimulationAccount, SimulationPosition


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
                    avg_3w real not null default 0,
                    ma20 real not null,
                    ma60 real not null,
                    ma120 real not null default 0,
                    discount_pct real not null,
                    three_week_position_pct real not null default 0,
                    pullback_from_3w_high_pct real not null default 0,
                    range_position_120d_pct real not null default 0,
                    pullback_from_120d_high_pct real not null default 0,
                    rsi14 real not null default 50,
                    five_day_return_pct real not null,
                    reasons text not null,
                    score_details text not null default '',
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

                create table if not exists simulation_account (
                    id integer primary key check (id = 1),
                    cash integer not null,
                    initial_cash integer not null,
                    updated_at text not null
                );

                create table if not exists simulation_trades (
                    id integer primary key autoincrement,
                    proposal_id integer,
                    side text not null,
                    symbol text not null,
                    name text not null,
                    trade_date text not null,
                    price integer not null,
                    quantity integer not null,
                    amount integer not null,
                    fee integer not null,
                    created_at text not null
                );

                create table if not exists simulation_positions (
                    symbol text primary key,
                    name text not null,
                    quantity integer not null,
                    avg_price real not null,
                    invested_amount integer not null,
                    updated_at text not null
                );
                """
            )
            self._ensure_column(conn, "signal_daily", "avg_3w", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "ma120", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "three_week_position_pct", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "pullback_from_3w_high_pct", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "range_position_120d_pct", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "pullback_from_120d_high_pct", "real not null default 0")
            self._ensure_column(conn, "signal_daily", "rsi14", "real not null default 50")
            self._ensure_column(conn, "signal_daily", "score_details", "text not null default ''")

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
                     avg_3m, avg_3w, ma20, ma60, ma120, discount_pct,
                     three_week_position_pct, pullback_from_3w_high_pct,
                     range_position_120d_pct, pullback_from_120d_high_pct, rsi14,
                     five_day_return_pct, reasons, score_details, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    date.today().isoformat(),
                    signal.score,
                    signal.label,
                    signal.buy_ratio,
                    signal.current_price,
                    signal.avg_3m,
                    signal.avg_3w,
                    signal.ma20,
                    signal.ma60,
                    signal.ma120,
                    signal.discount_pct,
                    signal.three_week_position_pct,
                    signal.pullback_from_3w_high_pct,
                    signal.range_position_120d_pct,
                    signal.pullback_from_120d_high_pct,
                    signal.rsi14,
                    signal.five_day_return_pct,
                    "\n".join(signal.reasons),
                    "\n".join(signal.score_details),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

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

    def has_recent_active_proposal(self, symbol: str, cooldown_minutes: int) -> bool:
        cutoff = datetime.now().timestamp() - cooldown_minutes * 60
        with self.connect() as conn:
            rows = conn.execute(
                """
                select created_at
                from proposals
                where symbol = ?
                  and status in ('pending', 'approved')
                order by created_at desc
                limit 20
                """,
                (symbol,),
            ).fetchall()
        for row in rows:
            try:
                created_at = datetime.fromisoformat(row["created_at"]).timestamp()
            except ValueError:
                continue
            if created_at >= cutoff:
                return True
        return False

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

    def list_telegram_authorized_chat_ids(self) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute("select chat_id from telegram_authorized_chats order by authorized_at").fetchall()
        return [int(row["chat_id"]) for row in rows]

    def ensure_simulation_account(self, initial_cash: int) -> SimulationAccount:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            row = conn.execute("select cash, initial_cash, updated_at from simulation_account where id = 1").fetchone()
            if row is None:
                conn.execute(
                    """
                    insert into simulation_account (id, cash, initial_cash, updated_at)
                    values (1, ?, ?, ?)
                    """,
                    (initial_cash, initial_cash, now),
                )
                return SimulationAccount(cash=initial_cash, initial_cash=initial_cash, updated_at=datetime.fromisoformat(now))
            return _simulation_account_from_row(row)

    def get_simulation_account(self) -> SimulationAccount | None:
        with self.connect() as conn:
            row = conn.execute("select cash, initial_cash, updated_at from simulation_account where id = 1").fetchone()
        return _simulation_account_from_row(row) if row else None

    def buy_simulation_position(
        self,
        proposal_id: int | None,
        symbol: str,
        name: str,
        price: int,
        quantity: int,
        fee: int,
    ) -> tuple[SimulationAccount, SimulationPosition]:
        amount = price * quantity
        total_cost = amount + fee
        trade_date = date.today().isoformat()
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            account_row = conn.execute("select cash, initial_cash, updated_at from simulation_account where id = 1").fetchone()
            if account_row is None:
                raise RuntimeError("Simulation account is not initialized.")
            if account_row["cash"] < total_cost:
                raise RuntimeError(f"Simulation cash is not enough. cash={account_row['cash']}, required={total_cost}")

            position_row = conn.execute(
                "select symbol, name, quantity, avg_price, invested_amount, updated_at from simulation_positions where symbol = ?",
                (symbol,),
            ).fetchone()
            if position_row is None:
                new_quantity = quantity
                new_invested = total_cost
            else:
                new_quantity = position_row["quantity"] + quantity
                new_invested = position_row["invested_amount"] + total_cost
            new_avg_price = new_invested / new_quantity if new_quantity else 0
            new_cash = account_row["cash"] - total_cost

            conn.execute(
                """
                insert into simulation_trades
                    (proposal_id, side, symbol, name, trade_date, price, quantity, amount, fee, created_at)
                values (?, 'BUY', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (proposal_id, symbol, name, trade_date, price, quantity, amount, fee, now),
            )
            conn.execute(
                """
                insert into simulation_positions
                    (symbol, name, quantity, avg_price, invested_amount, updated_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(symbol) do update set
                    name=excluded.name,
                    quantity=excluded.quantity,
                    avg_price=excluded.avg_price,
                    invested_amount=excluded.invested_amount,
                    updated_at=excluded.updated_at
                """,
                (symbol, name, new_quantity, new_avg_price, new_invested, now),
            )
            conn.execute(
                "update simulation_account set cash = ?, updated_at = ? where id = 1",
                (new_cash, now),
            )

        account = SimulationAccount(cash=new_cash, initial_cash=account_row["initial_cash"], updated_at=datetime.fromisoformat(now))
        position = SimulationPosition(
            symbol=symbol,
            name=name,
            quantity=new_quantity,
            avg_price=new_avg_price,
            invested_amount=new_invested,
            updated_at=datetime.fromisoformat(now),
        )
        return account, position

    def list_simulation_positions(self) -> list[SimulationPosition]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select symbol, name, quantity, avg_price, invested_amount, updated_at
                from simulation_positions
                order by symbol
                """
            ).fetchall()
        return [_simulation_position_from_row(row) for row in rows]


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


def _simulation_account_from_row(row: sqlite3.Row) -> SimulationAccount:
    return SimulationAccount(
        cash=row["cash"],
        initial_cash=row["initial_cash"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _simulation_position_from_row(row: sqlite3.Row) -> SimulationPosition:
    return SimulationPosition(
        symbol=row["symbol"],
        name=row["name"],
        quantity=row["quantity"],
        avg_price=row["avg_price"],
        invested_amount=row["invested_amount"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
