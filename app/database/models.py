"""Database models and queries."""

from datetime import datetime, date
from typing import List, Dict, Optional
from decimal import Decimal
from pydantic import BaseModel


class Instrument(BaseModel):
    """Instrument model."""

    id: Optional[int] = None
    token: int
    symbol: str
    exchange: str
    segment: str
    instrument_type: Optional[str] = None
    expiry: Optional[date] = None
    strike: Optional[Decimal] = None
    option_type: Optional[str] = None
    lot_size: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TickData(BaseModel):
    """Tick data model."""

    time: datetime
    instrument_token: int
    ltp: Optional[Decimal] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_qty: Optional[int] = None
    ask_qty: Optional[int] = None


class Candle(BaseModel):
    """Candle data model."""

    bucket: datetime
    instrument_token: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    open_interest: Optional[int] = None


class InstrumentQueries:
    """Database queries for instruments."""

    @staticmethod
    async def insert_instrument(pool, instrument: Instrument) -> int:
        """Insert instrument into database."""
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                """
                INSERT INTO instruments 
                (token, symbol, exchange, segment, instrument_type, expiry, strike, option_type, lot_size)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (token) DO UPDATE 
                SET symbol = EXCLUDED.symbol,
                    exchange = EXCLUDED.exchange,
                    segment = EXCLUDED.segment,
                    instrument_type = EXCLUDED.instrument_type,
                    expiry = EXCLUDED.expiry,
                    strike = EXCLUDED.strike,
                    option_type = EXCLUDED.option_type,
                    lot_size = EXCLUDED.lot_size,
                    updated_at = NOW()
                RETURNING id
            """,
                instrument.token,
                instrument.symbol,
                instrument.exchange,
                instrument.segment,
                instrument.instrument_type,
                instrument.expiry,
                instrument.strike,
                instrument.option_type,
                instrument.lot_size,
            )
            return result

    @staticmethod
    async def get_instrument_by_token(pool, token: int) -> Optional[Dict]:
        """Get instrument by token."""
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM instruments WHERE token = $1
            """,
                token,
            )
            return dict(result) if result else None

    @staticmethod
    async def get_all_instruments(
        pool, limit: int = 1000, offset: int = 0
    ) -> List[Dict]:
        """Get all instruments."""
        async with pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM instruments 
                ORDER BY symbol
                LIMIT $1 OFFSET $2
            """,
                limit,
                offset,
            )
            return [dict(row) for row in results]

    @staticmethod
    async def search_instruments(pool, query: str, limit: int = 50) -> List[Dict]:
        """Search instruments by symbol."""
        async with pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM instruments 
                WHERE symbol ILIKE $1 OR exchange ILIKE $1
                ORDER BY symbol
                LIMIT $2
            """,
                f"%{query}%",
                limit,
            )
            return [dict(row) for row in results]


class TickDataQueries:
    """Database queries for tick data."""

    @staticmethod
    async def bulk_insert_ticks(pool, ticks: List[tuple]):
        """Bulk insert tick data."""
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO tick_data 
                (time, instrument_token, ltp, volume, open_interest, 
                 bid_price, ask_price, bid_qty, ask_qty)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                ticks,
            )

    @staticmethod
    async def get_latest_tick(pool, instrument_token: int) -> Optional[Dict]:
        """Get latest tick for instrument."""
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM tick_data 
                WHERE instrument_token = $1 
                ORDER BY time DESC 
                LIMIT 1
            """,
                instrument_token,
            )
            return dict(result) if result else None

    @staticmethod
    async def get_ticks_range(
        pool, instrument_token: int, start_time: datetime, end_time: datetime
    ) -> List[Dict]:
        """Get ticks for instrument in time range."""
        async with pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM tick_data 
                WHERE instrument_token = $1 
                AND time >= $2 AND time <= $3
                ORDER BY time ASC
            """,
                instrument_token,
                start_time,
                end_time,
            )
            return [dict(row) for row in results]


class CandleQueries:
    """Database queries for candle data."""

    @staticmethod
    async def refresh_continuous_aggregates(
        pool, start_time: datetime, end_time: datetime
    ):
        """Manually refresh continuous aggregates for a time range."""
        async with pool.acquire() as conn:
            # Refresh all continuous aggregates
            await conn.execute(
                """
                CALL refresh_continuous_aggregate('candles_1m', $1, $2);
            """,
                start_time,
                end_time,
            )
            await conn.execute(
                """
                CALL refresh_continuous_aggregate('candles_5m', $1, $2);
            """,
                start_time,
                end_time,
            )
            await conn.execute(
                """
                CALL refresh_continuous_aggregate('candles_15m', $1, $2);
            """,
                start_time,
                end_time,
            )

    @staticmethod
    async def get_candles(
        pool,
        instrument_token: int,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict]:
        """Get candles for instrument."""
        table_name = f"candles_{interval}"
        async with pool.acquire() as conn:
            results = await conn.fetch(
                f"""
                SELECT * FROM {table_name}
                WHERE instrument_token = $1 
                AND bucket >= $2 AND bucket <= $3
                ORDER BY bucket ASC
            """,
                instrument_token,
                start_time,
                end_time,
            )
            return [dict(row) for row in results]


class SubscriptionQueries:
    """Database queries for subscriptions."""

    @staticmethod
    async def subscribe_instrument(pool, token: int):
        """Subscribe to instrument."""
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO subscribed_instruments (instrument_token, is_active)
                VALUES ($1, TRUE)
                ON CONFLICT (instrument_token) 
                DO UPDATE SET is_active = TRUE, subscribed_at = NOW()
            """,
                token,
            )

    @staticmethod
    async def unsubscribe_instrument(pool, token: int):
        """Unsubscribe from instrument."""
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE subscribed_instruments 
                SET is_active = FALSE 
                WHERE instrument_token = $1
            """,
                token,
            )

    @staticmethod
    async def get_subscribed_instruments(pool) -> List[int]:
        """Get all subscribed instrument tokens."""
        async with pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT instrument_token FROM subscribed_instruments 
                WHERE is_active = TRUE
            """
            )
            return [row["instrument_token"] for row in results]
