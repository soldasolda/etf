from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.models import DailyPrice, InvestmentSettings, Proposal, Signal, SimulationAccount, SimulationPosition


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
                    health_score integer not null default 0,
                    health_label text not null default '',
                    tactical_score integer not null default 0,
                    tactical_label text not null default '',
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
                    health_details text not null default '',
                    tactical_details text not null default '',
                    created_at text not null
                );

                create table if not exists proposals (
                    id integer primary key autoincrement,
                    symbol text not null,
                    name text not null,
                    proposal_type text not null default 'tactical',
                    cycle_month text,
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
                    proposal_type text not null default 'tactical',
                    cycle_month text,
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

                create table if not exists app_settings (
                    key text primary key,
                    value text not null,
                    updated_at text not null
                );

                create table if not exists benchmark_cycles (
                    cycle_month text primary key,
                    symbol text not null,
                    name text not null,
                    benchmark_date text not null,
                    price integer not null,
                    quantity integer not null,
                    amount integer not null,
                    leftover_cash integer not null,
                    total_budget integer not null,
                    created_at text not null
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
            self._ensure_column(conn, "signal_daily", "health_score", "integer not null default 0")
            self._ensure_column(conn, "signal_daily", "health_label", "text not null default ''")
            self._ensure_column(conn, "signal_daily", "tactical_score", "integer not null default 0")
            self._ensure_column(conn, "signal_daily", "tactical_label", "text not null default ''")
            self._ensure_column(conn, "signal_daily", "health_details", "text not null default ''")
            self._ensure_column(conn, "signal_daily", "tactical_details", "text not null default ''")
            self._ensure_column(conn, "proposals", "proposal_type", "text not null default 'tactical'")
            self._ensure_column(conn, "proposals", "cycle_month", "text")
            self._ensure_column(conn, "simulation_trades", "proposal_type", "text not null default 'tactical'")
            self._ensure_column(conn, "simulation_trades", "cycle_month", "text")

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
                    (symbol, signal_date, score, label,
                     health_score, health_label, tactical_score, tactical_label,
                     buy_ratio, current_price,
                     avg_3m, avg_3w, ma20, ma60, ma120, discount_pct,
                     three_week_position_pct, pullback_from_3w_high_pct,
                     range_position_120d_pct, pullback_from_120d_high_pct, rsi14,
                     five_day_return_pct, reasons, score_details,
                     health_details, tactical_details, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    date.today().isoformat(),
                    signal.score,
                    signal.label,
                    signal.health_score,
                    signal.health_label,
                    signal.tactical_score,
                    signal.tactical_label,
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
                    "\n".join(signal.health_details),
                    "\n".join(signal.tactical_details),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

    def create_proposal(
        self,
        symbol: str,
        name: str,
        signal: Signal,
        proposal_type: str = "tactical",
        cycle_month: str | None = None,
        amount_override: int | None = None,
        quantity_override: int | None = None,
    ) -> int | None:
        proposed_amount = amount_override if amount_override is not None else signal.tactical_amount
        proposed_quantity = quantity_override if quantity_override is not None else signal.expected_quantity
        if proposed_quantity <= 0 or proposed_amount <= 0:
            return None
        with self.connect() as conn:
            cursor = conn.execute(
                """
                insert into proposals
                    (symbol, name, proposal_type, cycle_month, status, proposed_price, proposed_amount,
                     proposed_quantity, score, label, created_at)
                values (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    name,
                    proposal_type,
                    cycle_month,
                    signal.current_price,
                    proposed_amount,
                    proposed_quantity,
                    signal.score,
                    signal.label,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)

    def has_recent_active_proposal(
        self,
        symbol: str,
        cooldown_minutes: int,
        proposal_type: str | None = None,
        cycle_month: str | None = None,
    ) -> bool:
        cutoff = datetime.now().timestamp() - cooldown_minutes * 60
        type_clause = "and proposal_type = ?" if proposal_type is not None else ""
        cycle_clause = "and cycle_month = ?" if cycle_month is not None else ""
        params_list: list[object] = [symbol]
        if proposal_type is not None:
            params_list.append(proposal_type)
        if cycle_month is not None:
            params_list.append(cycle_month)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                select created_at
                from proposals
                where symbol = ?
                  {type_clause}
                  {cycle_clause}
                  and status in ('pending', 'approved')
                order by created_at desc
                limit 20
                """,
                tuple(params_list),
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
                       proposed_amount, proposed_quantity, score, label,
                       proposal_type, cycle_month
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
                       proposed_amount, proposed_quantity, score, label,
                       proposal_type, cycle_month
                from proposals
                where id = ?
                """,
                (proposal_id,),
            ).fetchone()
        return _proposal_from_row(row) if row else None

    def has_cycle_proposal(self, symbol: str, cycle_month: str, proposal_type: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                select id from proposals
                where symbol = ? and cycle_month = ? and proposal_type = ?
                  and status in ('pending', 'approved')
                limit 1
                """,
                (symbol, cycle_month, proposal_type),
            ).fetchone()
        return row is not None

    def get_monthly_tactical_spent(self, cycle_month: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                select coalesce(sum(amount + fee), 0) as total
                from simulation_trades
                where cycle_month = ?
                  and proposal_type = 'tactical'
                  and side = 'BUY'
                """,
                (cycle_month,),
            ).fetchone()
        return int(row["total"] if row else 0)

    def ensure_benchmark_cycle(
        self,
        cycle_month: str,
        symbol: str,
        name: str,
        benchmark_date: date,
        price: int,
        total_budget: int,
    ) -> None:
        quantity = total_budget // price if price > 0 else 0
        amount = quantity * price
        leftover_cash = total_budget - amount
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                insert into benchmark_cycles
                    (cycle_month, symbol, name, benchmark_date, price, quantity,
                     amount, leftover_cash, total_budget, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(cycle_month) do update set
                    benchmark_date=excluded.benchmark_date,
                    price=excluded.price,
                    quantity=excluded.quantity,
                    amount=excluded.amount,
                    leftover_cash=excluded.leftover_cash,
                    total_budget=excluded.total_budget
                where benchmark_cycles.benchmark_date > excluded.benchmark_date
                """,
                (
                    cycle_month,
                    symbol,
                    name,
                    benchmark_date.isoformat(),
                    price,
                    quantity,
                    amount,
                    leftover_cash,
                    total_budget,
                    now,
                ),
            )

    def get_benchmark_summary(self, cycle_month: str, current_price: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                select benchmark_date, price, quantity, amount, leftover_cash, total_budget
                from benchmark_cycles
                where cycle_month = ?
                """,
                (cycle_month,),
            ).fetchone()
            trade_row = conn.execute(
                """
                select coalesce(sum(quantity), 0) as quantity,
                       coalesce(sum(amount + fee), 0) as spent
                from simulation_trades
                where cycle_month = ?
                  and side = 'BUY'
                """,
                (cycle_month,),
            ).fetchone()
        if row is None:
            return None
        benchmark_value = int(row["quantity"] * current_price + row["leftover_cash"])
        total_budget = int(row["total_budget"])
        benchmark_profit = benchmark_value - total_budget
        dynamic_quantity = int(trade_row["quantity"] if trade_row else 0)
        dynamic_spent = int(trade_row["spent"] if trade_row else 0)
        dynamic_leftover = max(0, total_budget - dynamic_spent)
        dynamic_value = int(dynamic_quantity * current_price + dynamic_leftover)
        dynamic_profit = dynamic_value - total_budget
        difference = dynamic_value - benchmark_value
        return (
            f"벤치마크({row['benchmark_date']} 전액 매수): "
            f"{row['quantity']:,}주 @ {row['price']:,}원, "
            f"현재가 기준 {benchmark_value:,}원 ({benchmark_profit:+,}원)\n"
            f"Dynamic DCA: {dynamic_quantity:,}주, 현재가 기준 {dynamic_value:,}원 "
            f"({dynamic_profit:+,}원), 벤치마크 대비 {difference:+,}원"
        )

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
        proposal_type: str = "tactical",
        cycle_month: str | None = None,
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
                    (proposal_id, proposal_type, cycle_month, side, symbol, name,
                     trade_date, price, quantity, amount, fee, created_at)
                values (?, ?, ?, 'BUY', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    proposal_type,
                    cycle_month,
                    symbol,
                    name,
                    trade_date,
                    price,
                    quantity,
                    amount,
                    fee,
                    now,
                ),
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

    def get_investment_settings(self, defaults: InvestmentSettings) -> InvestmentSettings:
        with self.connect() as conn:
            rows = conn.execute("select key, value from app_settings").fetchall()
        values = {row["key"]: row["value"] for row in rows}
        return InvestmentSettings(
            total_budget=int(values.get("total_budget", defaults.total_budget)),
            base_budget=int(values.get("base_budget", defaults.base_budget)),
            tactical_budget=int(values.get("tactical_budget", defaults.tactical_budget)),
            dca_day=int(values.get("dca_day", defaults.dca_day)),
        )

    def set_investment_settings(self, settings: InvestmentSettings) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        items = {
            "total_budget": str(settings.total_budget),
            "base_budget": str(settings.base_budget),
            "tactical_budget": str(settings.tactical_budget),
            "dca_day": str(settings.dca_day),
        }
        with self.connect() as conn:
            conn.executemany(
                """
                insert into app_settings (key, value, updated_at)
                values (?, ?, ?)
                on conflict(key) do update set
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                [(key, value, now) for key, value in items.items()],
            )

    def get_int_setting(self, key: str, default: int) -> int:
        with self.connect() as conn:
            row = conn.execute("select value from app_settings where key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return int(row["value"])
        except ValueError:
            return default

    def set_int_setting(self, key: str, value: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                insert into app_settings (key, value, updated_at)
                values (?, ?, ?)
                on conflict(key) do update set
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, str(value), now),
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
        proposal_type=row["proposal_type"],
        cycle_month=row["cycle_month"],
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
