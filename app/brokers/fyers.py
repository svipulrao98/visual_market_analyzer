"""Fyers API broker implementation."""
import asyncio
from typing import List, Dict, Callable, Optional
from datetime import datetime
from loguru import logger

try:
    from fyers_apiv3 import fyersModel
    from fyers_apiv3.FyersWebsocket import data_ws
except ImportError:
    fyersModel = None
    data_ws = None

from app.brokers.base import BrokerInterface
from app.config import settings


class FyersBroker(BrokerInterface):
    """Fyers API implementation."""
    
    def __init__(self):
        if not fyersModel or not data_ws:
            raise ImportError("fyers-apiv3 package not installed. Install with: pip install fyers-apiv3")
        
        if not settings.fyers_app_id or not settings.fyers_access_token:
            raise ValueError("Fyers API credentials not configured")
        
        self.client_id = settings.fyers_app_id
        self.access_token = settings.fyers_access_token
        self.fyers = fyersModel.FyersModel(
            client_id=self.client_id,
            token=self.access_token,
            is_async=False
        )
        self.ws: Optional[data_ws.FyersDataSocket] = None
        self.callback: Optional[Callable] = None
        self._subscribed_instruments: List[str] = []
        
        logger.info("Fyers broker initialized")
    
    async def connect_websocket(self, instruments: List[int], callback: Callable):
        """Connect to Fyers WebSocket."""
        self.callback = callback
        
        # Convert instrument tokens to Fyers format (needs to be mapped)
        # For now, assuming instruments are already in Fyers format
        fyers_symbols = [str(i) for i in instruments]
        self._subscribed_instruments = fyers_symbols
        
        def on_message(message):
            """Handle incoming messages."""
            if self.callback and isinstance(message, dict):
                asyncio.create_task(self._process_tick(message))
        
        def on_error(error):
            """Handle errors."""
            logger.error(f"Fyers WebSocket error: {error}")
        
        def on_close():
            """Handle close."""
            logger.warning("Fyers WebSocket closed")
        
        def on_open():
            """Handle connection."""
            logger.info("Fyers WebSocket connected")
        
        self.ws = data_ws.FyersDataSocket(
            access_token=self.access_token,
            run_background=False,
            log_path=""
        )
        
        self.ws.on_message = on_message
        self.ws.on_error = on_error
        self.ws.on_close = on_close
        self.ws.on_open = on_open
        
        # Subscribe to data
        data_type = "SymbolUpdate"
        self.ws.subscribe(symbols=fyers_symbols, data_type=data_type)
        
        # Connect in background
        await asyncio.get_event_loop().run_in_executor(None, self.ws.connect)
        logger.info("Fyers WebSocket connection established")
    
    async def _process_tick(self, tick: Dict):
        """Process and forward tick to callback."""
        try:
            tick_data = {
                'time': datetime.now(),
                'instrument_token': tick.get('symbol'),
                'ltp': tick.get('ltp'),
                'volume': tick.get('vol_traded_today'),
                'open_interest': tick.get('open_interest'),
                'bid_price': tick.get('bid_price'),
                'ask_price': tick.get('ask_price'),
                'bid_qty': tick.get('bid_qty'),
                'ask_qty': tick.get('ask_qty'),
            }
            await self.callback(tick_data)
        except Exception as e:
            logger.error(f"Error processing Fyers tick: {e}")
    
    async def disconnect_websocket(self):
        """Disconnect from WebSocket."""
        if self.ws:
            self.ws.close()
            logger.info("Fyers WebSocket disconnected")
    
    async def subscribe(self, instruments: List[int]):
        """Subscribe to instruments."""
        if self.ws:
            fyers_symbols = [str(i) for i in instruments]
            self.ws.subscribe(symbols=fyers_symbols, data_type="SymbolUpdate")
            self._subscribed_instruments.extend(fyers_symbols)
            logger.info(f"Subscribed to {len(instruments)} instruments")
    
    async def unsubscribe(self, instruments: List[int]):
        """Unsubscribe from instruments."""
        if self.ws:
            fyers_symbols = [str(i) for i in instruments]
            self.ws.unsubscribe(symbols=fyers_symbols)
            self._subscribed_instruments = [
                i for i in self._subscribed_instruments if i not in fyers_symbols
            ]
            logger.info(f"Unsubscribed from {len(instruments)} instruments")
    
    async def fetch_historical(
        self, 
        instrument: int, 
        from_date: datetime, 
        to_date: datetime, 
        interval: str
    ) -> List[Dict]:
        """Fetch historical data from Fyers."""
        try:
            # Map interval names
            interval_map = {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '1h': '60',
                '1d': 'D'
            }
            fyers_interval = interval_map.get(interval, interval)
            
            data = {
                "symbol": str(instrument),
                "resolution": fyers_interval,
                "date_format": "1",
                "range_from": from_date.strftime('%Y-%m-%d'),
                "range_to": to_date.strftime('%Y-%m-%d'),
                "cont_flag": "1"
            }
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.fyers.history,
                data
            )
            
            if response['s'] == 'ok':
                candles = []
                for i in range(len(response['t'])):
                    candles.append({
                        'time': datetime.fromtimestamp(response['t'][i]),
                        'open': response['o'][i],
                        'high': response['h'][i],
                        'low': response['l'][i],
                        'close': response['c'][i],
                        'volume': response['v'][i],
                        'open_interest': 0  # Fyers doesn't provide OI in history
                    })
                
                logger.info(f"Fetched {len(candles)} historical candles for {instrument}")
                return candles
            else:
                logger.error(f"Fyers historical data error: {response.get('message')}")
                return []
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return []
    
    async def get_instruments(self) -> List[Dict]:
        """Fetch instrument master from Fyers."""
        try:
            # Fyers doesn't have a direct instruments API
            # You would typically download the master CSV file
            logger.warning("Fyers instruments download not implemented. Use CSV download.")
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            return []
    
    async def get_quote(self, instruments: List[int]) -> Dict:
        """Get current quote for instruments."""
        try:
            symbols = ",".join([str(i) for i in instruments])
            data = {"symbols": symbols}
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.fyers.quotes,
                data
            )
            
            if response['s'] == 'ok':
                return response['d']
            else:
                logger.error(f"Fyers quote error: {response.get('message')}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            return {}

