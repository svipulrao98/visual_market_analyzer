"""Abstract broker interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Callable, Optional
from datetime import datetime


class BrokerInterface(ABC):
    """Base interface for broker implementations."""

    @abstractmethod
    async def connect_websocket(self, instruments: List[int], callback: Callable):
        """
        Connect to broker WebSocket and stream tick data.

        Args:
            instruments: List of instrument tokens to subscribe
            callback: Callback function to handle incoming ticks
        """
        pass

    @abstractmethod
    async def disconnect_websocket(self):
        """Disconnect from WebSocket."""
        pass

    @abstractmethod
    async def subscribe(self, instruments: List[int]):
        """Subscribe to instruments."""
        pass

    @abstractmethod
    async def unsubscribe(self, instruments: List[int]):
        """Unsubscribe from instruments."""
        pass

    @abstractmethod
    async def fetch_historical_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str,
    ) -> List[Dict]:
        """
        Fetch historical candle data from broker.

        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date
            interval: Candle interval (minute, 5minute, 15minute, 60minute, day)

        Returns:
            List of candle dictionaries with 'time', 'open', 'high', 'low', 'close', 'volume', 'open_interest'
        """
        pass

    @abstractmethod
    async def get_instruments(self) -> List[Dict]:
        """
        Fetch instrument master list from broker.

        Returns:
            List of instrument dictionaries
        """
        pass

    @abstractmethod
    async def get_quote(self, instruments: List[int]) -> Dict:
        """
        Get current quote for instruments.

        Args:
            instruments: List of instrument tokens

        Returns:
            Dictionary of quotes keyed by instrument token
        """
        pass
