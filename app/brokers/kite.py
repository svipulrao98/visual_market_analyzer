"""Kite Connect broker implementation."""

import asyncio
from typing import List, Dict, Callable, Optional
from datetime import datetime
from loguru import logger

try:
    from kiteconnect import KiteConnect, KiteTicker
except ImportError as e:
    logger.warning(
        f"KiteConnect import failed: {e}. Install with: pip install kiteconnect"
    )
    KiteConnect = None
    KiteTicker = None

from app.brokers.base import BrokerInterface
from app.brokers.auth.kite_auth import KiteAuth
from app.config import settings


class KiteBroker(BrokerInterface):
    """Kite Connect API implementation."""

    def __init__(self):
        if not KiteConnect or not KiteTicker:
            raise ImportError(
                "kiteconnect package not installed. Install with: pip install kiteconnect"
            )

        if not settings.kite_api_key:
            raise ValueError("KITE_API_KEY not configured in environment")

        # Initialize auth handler
        self.auth_handler = None
        if self._should_auto_authenticate():
            logger.info("Auto-authentication enabled for Kite")
            self.auth_handler = KiteAuth(
                api_key=settings.kite_api_key,
                api_secret=settings.kite_api_secret,
                username=settings.kite_username,
                password=settings.kite_password,
                totp_key=settings.kite_totp_key,
                access_token=settings.kite_access_token,
            )
        elif not settings.kite_access_token:
            raise ValueError(
                "KITE_ACCESS_TOKEN not configured and auto-auth credentials missing"
            )

        self.kite = KiteConnect(api_key=settings.kite_api_key)
        self.ticker: Optional[KiteTicker] = None
        self.callback: Optional[Callable] = None
        self._subscribed_instruments: List[int] = []

        logger.info("Kite broker initialized")

    def _should_auto_authenticate(self) -> bool:
        """Check if we should use auto-authentication."""
        return bool(
            settings.kite_api_secret
            and settings.kite_username
            and settings.kite_password
            and settings.kite_totp_key
        )

    async def _ensure_authenticated(self):
        """Ensure we have a valid access token."""
        if self.auth_handler:
            access_token = await self.auth_handler.get_valid_token()
            self.kite.set_access_token(access_token)
            # Update settings for other parts of the app
            settings.kite_access_token = access_token
        else:
            # Manual token
            if not settings.kite_access_token:
                raise ValueError("No access token available")
            self.kite.set_access_token(settings.kite_access_token)

    async def connect_websocket(self, instruments: List[int], callback: Callable):
        """Connect to Kite WebSocket."""
        # Ensure we have a valid token
        await self._ensure_authenticated()

        self.callback = callback
        self._subscribed_instruments = instruments

        self.ticker = KiteTicker(
            api_key=settings.kite_api_key, access_token=settings.kite_access_token
        )

        def on_ticks(ws, ticks):
            """Handle incoming ticks."""
            if self.callback:
                asyncio.create_task(self._process_ticks(ticks))

        def on_connect(ws, response):
            """Handle WebSocket connection."""
            logger.info(f"Kite WebSocket connected: {response}")
            ws.subscribe(instruments)
            ws.set_mode(ws.MODE_FULL, instruments)

        def on_close(ws, code, reason):
            """Handle WebSocket disconnection."""
            logger.warning(f"Kite WebSocket closed: {code} - {reason}")

        def on_error(ws, code, reason):
            """Handle WebSocket error."""
            logger.error(f"Kite WebSocket error: {code} - {reason}")

        self.ticker.on_ticks = on_ticks
        self.ticker.on_connect = on_connect
        self.ticker.on_close = on_close
        self.ticker.on_error = on_error

        # Run ticker in background thread
        await asyncio.get_event_loop().run_in_executor(None, self.ticker.connect, True)
        logger.info("Kite WebSocket connection established")

    async def _process_ticks(self, ticks: List[Dict]):
        """Process and forward ticks to callback."""
        for tick in ticks:
            tick_data = {
                "time": datetime.now(),
                "instrument_token": tick.get("instrument_token"),
                "ltp": tick.get("last_price"),
                "volume": tick.get("volume"),
                "open_interest": tick.get("oi"),
                "bid_price": (
                    tick.get("depth", {}).get("buy", [{}])[0].get("price")
                    if tick.get("depth")
                    else None
                ),
                "ask_price": (
                    tick.get("depth", {}).get("sell", [{}])[0].get("price")
                    if tick.get("depth")
                    else None
                ),
                "bid_qty": (
                    tick.get("depth", {}).get("buy", [{}])[0].get("quantity")
                    if tick.get("depth")
                    else None
                ),
                "ask_qty": (
                    tick.get("depth", {}).get("sell", [{}])[0].get("quantity")
                    if tick.get("depth")
                    else None
                ),
            }
            await self.callback(tick_data)

    async def disconnect_websocket(self):
        """Disconnect from WebSocket."""
        if self.ticker:
            self.ticker.close()
            logger.info("Kite WebSocket disconnected")

    async def subscribe(self, instruments: List[int]):
        """Subscribe to instruments."""
        if self.ticker and self.ticker.is_connected():
            self.ticker.subscribe(instruments)
            self.ticker.set_mode(self.ticker.MODE_FULL, instruments)
            self._subscribed_instruments.extend(instruments)
            logger.info(f"Subscribed to {len(instruments)} instruments")

    async def unsubscribe(self, instruments: List[int]):
        """Unsubscribe from instruments."""
        if self.ticker and self.ticker.is_connected():
            self.ticker.unsubscribe(instruments)
            self._subscribed_instruments = [
                i for i in self._subscribed_instruments if i not in instruments
            ]
            logger.info(f"Unsubscribed from {len(instruments)} instruments")

    async def fetch_historical(
        self, instrument: int, from_date: datetime, to_date: datetime, interval: str
    ) -> List[Dict]:
        """Fetch historical data from Kite."""
        # Ensure we have a valid token
        await self._ensure_authenticated()

        try:
            # Map interval names
            interval_map = {
                "1m": "minute",
                "5m": "5minute",
                "15m": "15minute",
                "1h": "60minute",
                "1d": "day",
            }
            kite_interval = interval_map.get(interval, interval)

            data = await asyncio.get_event_loop().run_in_executor(
                None,
                self.kite.historical_data,
                instrument,
                from_date.strftime("%Y-%m-%d"),
                to_date.strftime("%Y-%m-%d"),
                kite_interval,
            )

            # Convert to standard format
            candles = []
            for candle in data:
                candles.append(
                    {
                        "time": candle["date"],
                        "open": candle["open"],
                        "high": candle["high"],
                        "low": candle["low"],
                        "close": candle["close"],
                        "volume": candle["volume"],
                        "open_interest": candle.get("oi", 0),
                    }
                )

            logger.info(f"Fetched {len(candles)} historical candles for {instrument}")
            return candles

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return []

    async def get_instruments(self) -> List[Dict]:
        """Fetch instrument master from Kite."""
        # Ensure we have a valid token
        await self._ensure_authenticated()

        try:
            instruments = await asyncio.get_event_loop().run_in_executor(
                None, self.kite.instruments
            )

            # Convert to standard format
            formatted_instruments = []
            for inst in instruments:
                formatted_instruments.append(
                    {
                        "token": inst["instrument_token"],
                        "symbol": inst["tradingsymbol"],
                        "exchange": inst["exchange"],
                        "segment": inst["segment"],
                        "instrument_type": inst["instrument_type"],
                        "expiry": inst["expiry"] if inst["expiry"] else None,
                        "strike": inst["strike"] if inst["strike"] else None,
                        "option_type": (
                            inst["instrument_type"]
                            if inst["instrument_type"] in ["CE", "PE"]
                            else None
                        ),
                        "lot_size": inst["lot_size"],
                    }
                )

            logger.info(f"Fetched {len(formatted_instruments)} instruments")
            return formatted_instruments

        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            return []

    async def get_quote(self, instruments: List[int]) -> Dict:
        """Get current quote for instruments."""
        # Ensure we have a valid token
        await self._ensure_authenticated()

        try:
            # Convert tokens to exchange:symbol format if needed
            quotes = await asyncio.get_event_loop().run_in_executor(
                None, self.kite.quote, [str(i) for i in instruments]
            )
            return quotes
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            return {}
