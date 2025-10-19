# Trading Helper System - Technical Specification

> **🔥 UPDATED ARCHITECTURE - KEY CHANGES FROM ORIGINAL DESIGN:**
> 
> **MAJOR CHANGE #1: Multi-Timeframe Strategy**
> - ✅ NEW: Store tick-by-tick data during live market
> - ✅ NEW: TimescaleDB continuous aggregates auto-create ALL timeframes (1m, 5m, 15m, 1h, 1d)
> - ✅ NEW: Zero processing in FastAPI - database handles ALL aggregation
> - ✅ NEW: Grafana queries appropriate materialized view based on user's timeframe selection
> - ❌ REMOVED: Separate backfill API endpoint
> 
> **MAJOR CHANGE #2: Smart Data Flow**
> - ✅ NEW: On-demand gap filling in candle endpoint (no separate backfill endpoint)
> - ✅ NEW: Historical data fetched automatically when gaps detected
> - ✅ NEW: Single `/api/candles` endpoint handles both DB queries and broker backfill
> - ❌ REMOVED: Manual backfill trigger
>
> **CRITICAL FILES TO FOCUS ON:**
> 1. `app/database/schema.sql` - Contains ALL 5 continuous aggregate definitions
> 2. `app/services/candle_service.py` - Gap detection and smart backfill logic
> 3. `app/api/candles.py` - Single endpoint for all candle queries
> 4. `app/services/data_ingestion.py` - Tick buffering and batch insert

## Project Overview
A real-time trading data ingestion and visualization system supporting Kite and Fyers APIs. The system captures tick-by-tick market data, stores it in TimescaleDB with automatic multi-timeframe aggregation, and provides Grafana dashboards for analysis.

## Tech Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: TimescaleDB (PostgreSQL 15 + TimescaleDB extension)
- **Cache/Queue**: Redis 7.x
- **Visualization**: Grafana 10.x
- **Orchestration**: Docker Compose
- **Deployment**: Local (future: AWS)

## System Architecture

```
┌─────────────────┐
│  Kite/Fyers WS  │ (Tick-by-tick data)
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────┐
│   FastAPI App   │◄────►│  Redis   │
│  (Tick Buffer)  │      └──────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│         TimescaleDB                 │
│  ┌──────────────────────────────┐  │
│  │  tick_data (hypertable)      │  │
│  └──────────┬───────────────────┘  │
│             ▼                       │
│  ┌──────────────────────────────┐  │
│  │  Continuous Aggregates:      │  │
│  │  - candles_1m                │  │
│  │  - candles_5m                │  │
│  │  - candles_15m               │  │
│  │  - candles_1h                │  │
│  │  - candles_1d                │  │
│  └──────────────────────────────┘  │
└─────────────────┬───────────────────┘
                  │
                  ▼
         ┌─────────────────┐
         │    Grafana      │
         │ (Query views)   │
         └─────────────────┘
```

## Core Data Flow

### Live Market Hours
```
Broker WebSocket → FastAPI Buffer → tick_data table
                                         ↓
                    TimescaleDB Auto-Aggregates (background)
                                         ↓
                    candles_1m, 5m, 15m, 1h, 1d (materialized views)
                                         ↓
                                    Grafana Queries
```

### Historical Data / Gap Filling
```
Grafana requests data → FastAPI /api/candles endpoint
                              ↓
                     Check TimescaleDB
                              ↓
                    If gap exists → Fetch from Broker Historical API
                              ↓
                    Store as 1m candles → Return to Grafana
```

## Core Requirements

### 1. Data Sources
- **Kite API**: WebSocket for real-time tick data + Historical REST API
- **Fyers API**: WebSocket for real-time tick data + Historical REST API
- Support switching between brokers via configuration

### 2. Data Types & Instruments
- **Instruments**: NSE F&O (Index futures/options), Cash stocks, Stock futures
- **Real-time**: Tick-by-tick data (price, volume, OI, bid/ask, timestamp)
- **Historical**: 1-minute candles (OHLCV + OI) fetched on-demand
- **Estimated Volume**: 500-1000 instruments simultaneously

### 3. Multi-Timeframe Strategy
- **Tick data**: Raw tick-by-tick stored in `tick_data` hypertable
- **Automatic aggregation**: TimescaleDB continuous aggregates create:
  - 1-minute candles
  - 5-minute candles
  - 15-minute candles
  - 1-hour candles
  - 1-day candles
- **Zero processing in FastAPI**: All aggregation happens in database
- **Grafana queries**: Directly query the appropriate candle view based on user's timeframe selection

### 4. Data Retention Policy
```
tick_data:     7 days (compress after 1 day, delete after 7 days)
candles_1m:    30 days
candles_5m:    90 days
candles_15m:   6 months
candles_1h:    1 year
candles_1d:    Retain indefinitely
```

### 5. Performance Targets
- Handle 500-1000 instruments simultaneously
- Process ~1000 ticks per second during market hours
- Sub-second latency for tick ingestion
- Support single user, multiple browser tabs
- Zero data loss during WebSocket reconnections
- Blazing fast Grafana queries (pre-aggregated data)

## Project Structure

```
trading-helper/
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── README.md
│
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration management
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── instruments.py      # Instrument management endpoints
│   │   ├── candles.py          # Smart candle fetch (with gap filling)
│   │   └── websocket.py        # WebSocket endpoints
│   │
│   ├── brokers/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract broker interface
│   │   ├── kite.py             # Kite API implementation
│   │   └── fyers.py            # Fyers API implementation
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py       # DB connection pool
│   │   ├── models.py           # SQLAlchemy models
│   │   └── schema.sql          # TimescaleDB schema (CRITICAL FILE)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_ingestion.py  # Real-time tick handler with buffering
│   │   ├── candle_service.py  # Gap detection & backfill logic
│   │   └── instruments.py      # Instrument management
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Logging configuration
│       └── redis_client.py     # Redis connection
│
├── grafana/
│   ├── dashboards/
│   │   └── market_overview.json
│   └── provisioning/
│       ├── datasources/
│       │   └── timescaledb.yml
│       └── dashboards/
│           └── dashboard.yml
│
└── scripts/
    ├── init_db.py              # Database initialization
    └── seed_instruments.py     # Load instrument master
```

## Docker Compose Services

### docker-compose.yml
```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: trading_timescaledb
    environment:
      POSTGRES_DB: trading_data
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: trading_secure_password_2024
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
      - ./app/database/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trading_user -d trading_data"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: trading_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  fastapi:
    build: .
    container_name: trading_fastapi
    environment:
      DATABASE_URL: postgresql://trading_user:trading_secure_password_2024@timescaledb:5432/trading_data
      REDIS_URL: redis://redis:6379
      BROKER: kite
      KITE_API_KEY: ${KITE_API_KEY}
      KITE_ACCESS_TOKEN: ${KITE_ACCESS_TOKEN}
      FYERS_APP_ID: ${FYERS_APP_ID}
      FYERS_ACCESS_TOKEN: ${FYERS_ACCESS_TOKEN}
      LOG_LEVEL: INFO
      TICK_BUFFER_SIZE: 1000
      FLUSH_INTERVAL_SECONDS: 1
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: trading_grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: ""
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    ports:
      - "3000:3000"
    depends_on:
      - timescaledb
    restart: unless-stopped

volumes:
  timescaledb_data:
  redis_data:
  grafana_data:

networks:
  default:
    name: trading_network
```

## Database Schema (CRITICAL)

### app/database/schema.sql
```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- INSTRUMENTS MASTER TABLE
-- ============================================
CREATE TABLE instruments (
    id SERIAL PRIMARY KEY,
    token INTEGER UNIQUE NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    segment VARCHAR(20) NOT NULL,  -- CASH, FUT, OPT
    instrument_type VARCHAR(10),    -- INDEX, STOCK, etc.
    expiry DATE,
    strike DECIMAL(10,2),
    option_type CHAR(2),            -- CE, PE
    lot_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_instruments_token ON instruments(token);
CREATE INDEX idx_instruments_symbol ON instruments(symbol);
CREATE INDEX idx_instruments_exchange_segment ON instruments(exchange, segment);

-- ============================================
-- TICK DATA (HYPERTABLE) - RAW TICK-BY-TICK
-- ============================================
CREATE TABLE tick_data (
    time TIMESTAMPTZ NOT NULL,
    instrument_token INTEGER NOT NULL,
    ltp DECIMAL(12,2),
    volume BIGINT,
    open_interest BIGINT,
    bid_price DECIMAL(12,2),
    ask_price DECIMAL(12,2),
    bid_qty INTEGER,
    ask_qty INTEGER
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('tick_data', 'time');

-- Index for faster queries
CREATE INDEX idx_tick_data_instrument_time 
    ON tick_data (instrument_token, time DESC);

-- Compression policy (compress chunks older than 1 day)
ALTER TABLE tick_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_token',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('tick_data', INTERVAL '1 day');

-- Retention policy (drop chunks older than 7 days)
SELECT add_retention_policy('tick_data', INTERVAL '7 days');

-- ============================================
-- CONTINUOUS AGGREGATE: 1-MINUTE CANDLES
-- ============================================
CREATE MATERIALIZED VIEW candles_1m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 minute', time) AS bucket,
    instrument_token,
    FIRST(ltp, time) AS open,
    MAX(ltp) AS high,
    MIN(ltp) AS low,
    LAST(ltp, time) AS close,
    SUM(volume) AS volume,
    LAST(open_interest, time) AS open_interest
FROM tick_data
GROUP BY bucket, instrument_token;

-- Index for faster queries
CREATE INDEX idx_candles_1m_instrument_bucket 
    ON candles_1m (instrument_token, bucket DESC);

-- Refresh policy (refresh every 1 minute, lag 1 minute)
SELECT add_continuous_aggregate_policy('candles_1m',
    start_offset => INTERVAL '2 minutes',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

-- Retention policy (drop data older than 30 days)
SELECT add_retention_policy('candles_1m', INTERVAL '30 days');

-- ============================================
-- CONTINUOUS AGGREGATE: 5-MINUTE CANDLES
-- ============================================
CREATE MATERIALIZED VIEW candles_5m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', bucket) AS bucket,
    instrument_token,
    FIRST(open, bucket) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, bucket) AS close,
    SUM(volume) AS volume,
    LAST(open_interest, bucket) AS open_interest
FROM candles_1m
GROUP BY time_bucket('5 minutes', bucket), instrument_token;

CREATE INDEX idx_candles_5m_instrument_bucket 
    ON candles_5m (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_5m',
    start_offset => INTERVAL '10 minutes',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

SELECT add_retention_policy('candles_5m', INTERVAL '90 days');

-- ============================================
-- CONTINUOUS AGGREGATE: 15-MINUTE CANDLES
-- ============================================
CREATE MATERIALIZED VIEW candles_15m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('15 minutes', bucket) AS bucket,
    instrument_token,
    FIRST(open, bucket) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, bucket) AS close,
    SUM(volume) AS volume,
    LAST(open_interest, bucket) AS open_interest
FROM candles_5m
GROUP BY time_bucket('15 minutes', bucket), instrument_token;

CREATE INDEX idx_candles_15m_instrument_bucket 
    ON candles_15m (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_15m',
    start_offset => INTERVAL '30 minutes',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');

SELECT add_retention_policy('candles_15m', INTERVAL '6 months');

-- ============================================
-- CONTINUOUS AGGREGATE: 1-HOUR CANDLES
-- ============================================
CREATE MATERIALIZED VIEW candles_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', bucket) AS bucket,
    instrument_token,
    FIRST(open, bucket) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, bucket) AS close,
    SUM(volume) AS volume,
    LAST(open_interest, bucket) AS open_interest
FROM candles_15m
GROUP BY time_bucket('1 hour', bucket), instrument_token;

CREATE INDEX idx_candles_1h_instrument_bucket 
    ON candles_1h (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_1h',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

SELECT add_retention_policy('candles_1h', INTERVAL '1 year');

-- ============================================
-- CONTINUOUS AGGREGATE: 1-DAY CANDLES
-- ============================================
CREATE MATERIALIZED VIEW candles_1d
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', bucket) AS bucket,
    instrument_token,
    FIRST(open, bucket) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, bucket) AS close,
    SUM(volume) AS volume,
    LAST(open_interest, bucket) AS open_interest
FROM candles_1h
GROUP BY time_bucket('1 day', bucket), instrument_token;

CREATE INDEX idx_candles_1d_instrument_bucket 
    ON candles_1d (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- No retention policy for daily candles (keep forever)

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to get candle data for any timeframe
CREATE OR REPLACE FUNCTION get_candles(
    p_instrument_token INTEGER,
    p_from_time TIMESTAMPTZ,
    p_to_time TIMESTAMPTZ,
    p_interval TEXT DEFAULT '1m'
)
RETURNS TABLE (
    bucket TIMESTAMPTZ,
    open DECIMAL,
    high DECIMAL,
    low DECIMAL,
    close DECIMAL,
    volume BIGINT,
    open_interest BIGINT
) AS $$
BEGIN
    RETURN QUERY EXECUTE format(
        'SELECT bucket, open, high, low, close, volume, open_interest 
         FROM candles_%s 
         WHERE instrument_token = $1 
           AND bucket >= $2 
           AND bucket <= $3 
         ORDER BY bucket',
        p_interval
    ) USING p_instrument_token, p_from_time, p_to_time;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- INITIAL DATA / COMMENTS
-- ============================================

COMMENT ON TABLE tick_data IS 'Raw tick-by-tick data from broker WebSocket. Compressed after 1 day, deleted after 7 days.';
COMMENT ON MATERIALIZED VIEW candles_1m IS '1-minute OHLCV candles. Auto-aggregated from tick_data. Retained for 30 days.';
COMMENT ON MATERIALIZED VIEW candles_5m IS '5-minute OHLCV candles. Auto-aggregated from candles_1m. Retained for 90 days.';
COMMENT ON MATERIALIZED VIEW candles_15m IS '15-minute OHLCV candles. Auto-aggregated from candles_5m. Retained for 6 months.';
COMMENT ON MATERIALIZED VIEW candles_1h IS '1-hour OHLCV candles. Auto-aggregated from candles_15m. Retained for 1 year.';
COMMENT ON MATERIALIZED VIEW candles_1d IS '1-day OHLCV candles. Auto-aggregated from candles_1h. Retained indefinitely.';
```

## FastAPI Implementation

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### requirements.txt
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
asyncpg==0.29.0
redis==5.0.1
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
websockets==12.0
httpx==0.25.2
```

### app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api import instruments, candles, websocket
from app.database.connection import init_db, close_db
from app.utils.logger import setup_logger
from app.services.data_ingestion import DataIngestionService

# Global ingestion service
ingestion_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global ingestion_service
    await init_db()
    setup_logger()
    ingestion_service = DataIngestionService()
    await ingestion_service.start()
    
    yield
    
    # Shutdown
    await ingestion_service.stop()
    await close_db()

app = FastAPI(
    title="Trading Helper API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Grafana
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(instruments.router, prefix="/api/instruments", tags=["instruments"])
app.include_router(candles.router, prefix="/api/candles", tags=["candles"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])

@app.get("/")
async def root():
    return {"message": "Trading Helper API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def get_ingestion_service() -> DataIngestionService:
    return ingestion_service
```

### app/config.py
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # Broker
    BROKER: str = "kite"  # or "fyers"
    
    # Kite API
    KITE_API_KEY: str = ""
    KITE_ACCESS_TOKEN: str = ""
    
    # Fyers API
    FYERS_APP_ID: str = ""
    FYERS_ACCESS_TOKEN: str = ""
    
    # Application
    LOG_LEVEL: str = "INFO"
    TICK_BUFFER_SIZE: int = 1000
    FLUSH_INTERVAL_SECONDS: int = 1
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### app/database/connection.py
```python
import asyncpg
from app.config import get_settings

settings = get_settings()
pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=10,
        max_size=20,
        command_timeout=60
    )

async def close_db():
    global pool
    if pool:
        await pool.close()

async def get_db_pool():
    return pool
```

### app/brokers/base.py
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Callable, Optional
from datetime import datetime

class BrokerInterface(ABC):
    """Abstract base class for broker implementations"""
    
    @abstractmethod
    async def connect_websocket(
        self, 
        instruments: List[int], 
        callback: Callable
    ) -> None:
        """
        Connect to broker WebSocket and stream tick data
        
        Args:
            instruments: List of instrument tokens to subscribe
            callback: Async function to call with each tick
        """
        pass
    
    @abstractmethod
    async def disconnect_websocket(self) -> None:
        """Disconnect from WebSocket"""
        pass
    
    @abstractmethod
    async def fetch_historical_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "minute"
    ) -> List[Dict]:
        """
        Fetch historical candle data
        
        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date
            interval: Candle interval (minute, 5minute, 15minute, etc.)
            
        Returns:
            List of candles with OHLCV data
        """
        pass
    
    @abstractmethod
    async def get_instruments(self) -> List[Dict]:
        """
        Fetch complete instrument master list
        
        Returns:
            List of instruments with tokens, symbols, etc.
        """
        pass
```

### app/services/data_ingestion.py
```python
import asyncio
from datetime import datetime
from typing import Dict
from app.database.connection import get_db_pool
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class DataIngestionService:
    """
    Handles buffering and batch insertion of tick data
    """
    
    def __init__(self):
        self.buffer = []
        self.buffer_size = settings.TICK_BUFFER_SIZE
        self.flush_interval = settings.FLUSH_INTERVAL_SECONDS
        self.running = False
        self.flush_task = None
    
    async def start(self):
        """Start the periodic flush loop"""
        self.running = True
        self.flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Data ingestion service started")
    
    async def stop(self):
        """Stop the service and flush remaining data"""
        self.running = False
        if self.flush_task:
            self.flush_task.cancel()
        await self.flush_buffer()
        logger.info("Data ingestion service stopped")
    
    async def handle_tick(self, tick_data: Dict):
        """
        Buffer incoming tick data
        
        Expected tick_data format:
        {
            'instrument_token': int,
            'timestamp': datetime,
            'ltp': float,
            'volume': int,
            'open_interest': int,
            'bid_price': float,
            'ask_price': float,
            'bid_qty': int,
            'ask_qty': int
        }
        """
        self.buffer.append(tick_data)
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self.flush_buffer()
    
    async def flush_buffer(self):
        """Bulk insert tick data to TimescaleDB"""
        if not self.buffer:
            return
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Prepare data for executemany
                records = [
                    (
                        tick['timestamp'],
                        tick['instrument_token'],
                        tick.get('ltp'),
                        tick.get('volume'),
                        tick.get('open_interest'),
                        tick.get('bid_price'),
                        tick.get('ask_price'),
                        tick.get('bid_qty'),
                        tick.get('ask_qty')
                    )
                    for tick in self.buffer
                ]
                
                await conn.executemany("""
                    INSERT INTO tick_data 
                    (time, instrument_token, ltp, volume, open_interest, 
                     bid_price, ask_price, bid_qty, ask_qty)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, records)
                
                logger.info(f"Flushed {len(records)} ticks to database")
                self.buffer.clear()
                
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
            # Keep buffer for retry
    
    async def _flush_loop(self):
        """Periodically flush buffer"""
        while self.running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")
```

### app/services/candle_service.py
```python
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.database.connection import get_db_pool
from app.brokers.base import BrokerInterface
from app.utils.logger import get_logger

logger = get_logger(__name__)

class CandleService:
    """
    Smart candle fetch with gap detection and backfill
    """
    
    def __init__(self, broker: BrokerInterface):
        self.broker = broker
    
    async def get_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1m"
    ) -> List[Dict]:
        """
        Get candles with automatic gap filling
        
        Args:
            instrument_token: Instrument token
            from_date: Start datetime
            to_date: End datetime
            interval: Timeframe (1m, 5m, 15m, 1h, 1d)
            
        Returns:
            List of candles
        """
        # Query database first
        db_candles = await self._query_db_candles(
            instrument_token, from_date, to_date, interval
        )
        
        # Detect gaps
        gaps = self._find_gaps(db_candles, from_date, to_date, interval)
        
        # Backfill gaps from broker
        if gaps:
            logger.info(f"Found {len(gaps)} gaps for {instrument_token}, backfilling...")
            for gap_start, gap_end in gaps:
                await self._backfill_gap(
                    instrument_token, gap_start, gap_end, interval
                )
            
            # Re-query after backfill
            db_candles = await self._query_db_candles(
                instrument_token, from_date, to_date, interval
            )
        
        return db_candles
    
    async def _query_db_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Query candles from TimescaleDB"""
        pool = await get_db_pool()
        
        # Map interval to table
        table_map = {
            "1m": "candles_1m",
            "5m": "candles_5m",
            "15m": "candles_15m",
            "1h": "candles_1h",
            "1d": "candles_1d"
        }
        
        table = table_map.get(interval, "candles_1m")
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT 
                    bucket,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    open_interest
                FROM {table}
                WHERE instrument_token = $1
                  AND bucket >= $2
                  AND bucket <= $3
                ORDER BY bucket
            """, instrument_token, from_date, to_date)
            
            return [dict(row) for row in rows]
    
    def _find_gaps(
        self,
        candles: List[Dict],
        from_date: datetime,
        to_date: datetime,
        interval: str
    ) -> List[tuple]:
        """
        Detect missing time periods in candle data
        
        Returns:
            List of (gap_start, gap_end) tuples
        """
        if not candles:
            return [(from_date, to_date)]
        
        # Map interval to timedelta
        interval_map = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1)
        }
        
        delta = interval_map.get(interval, timedelta(minutes=1))
        gaps = []
        
        # Check gap before first candle
        first_bucket = candles[0]['bucket']
        if first_bucket > from_date:
            gaps.append((from_date, first_bucket - delta))
        
        # Check gaps between candles
        for i in range(len(candles) - 1):
            current_bucket = candles[i]['bucket']
            next_bucket = candles[i + 1]['bucket']
            expected_next = current_bucket + delta
            
            if next_bucket > expected_next:
                gaps.append((expected_next, next_bucket - delta))
        
        # Check gap after last candle
        last_bucket = candles[-1]['bucket']
        if last_bucket < to_date:
            gaps.append((last_bucket + delta, to_date))
        
        return gaps
    
    async def _backfill_gap(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str
    ):
        """Fetch missing candles from broker and store"""
        try:
            # Map interval to broker API format
            broker_interval_map = {
                "1m": "minute",
                "5m": "5minute",
                "15m": "15minute",
                "1h": "60minute",
                "1d": "day"
            }
            
            broker_interval = broker_interval_map.get(interval, "minute")
            
            # Fetch from broker
            broker_candles = await self.broker.fetch_historical_candles(
                instrument_token,
                from_date,
                to_date,
                broker_interval
            )
            
            if not broker_candles:
                logger.warning(f"No data from broker for {instrument_token}")
                return
            
            # Store in database
            await self._store_candles(broker_candles, interval)
            
            logger.info(f"Backfilled {len(broker_candles)} candles for {instrument_token}")
            
        except Exception as e:
            logger.error(f"Error backfilling gap: {e}")
    
    async def _store_candles(self, candles: List[Dict], interval: str):
        """Store candles in appropriate TimescaleDB table"""
        pool = await get_db_pool()
        
        table_map = {
            "1m": "candles_1m",
            "5m": "candles_5m",
            "15m": "candles_15m",
            "1h": "candles_1h",
            "1d": "candles_1d"
        }
        
        table = table_map.get(interval, "candles_1m")
        
        async with pool.acquire() as conn:
            records = [
                (
                    c['timestamp'],
                    c['instrument_token'],
                    c['open'],
                    c['high'],
                    c['low'],
                    c['close'],
                    c['volume'],
                    c.get('open_interest', 0)
                )
                for c in candles
            ]
            
            # Insert directly into materialized view (manual refresh needed)
            await conn.executemany(f"""
                INSERT INTO {table} 
                (bucket, instrument_token, open, high, low, close, volume, open_interest)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (bucket, instrument_token) DO NOTHING
            """, records)
```

### app/api/candles.py
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict
from app.services.candle_service import CandleService
from app.brokers.base import BrokerInterface
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

class CandleRequest(BaseModel):
    instrument_token: int
    from_date: datetime
    to_date: datetime
    interval: str = "1m"  # 1m, 5m, 15m, 1h, 1d

# Dependency to get broker instance (implement based on config)
async def get_broker() -> BrokerInterface:
    from app.config import get_settings
    settings = get_settings()
    
    if settings.BROKER == "kite":
        from app.brokers.kite import KiteBroker
        return KiteBroker()
    elif settings.BROKER == "fyers":
        from app.brokers.fyers import FyersBroker
        return FyersBroker()
    else:
        raise HTTPException(status_code=500, detail="Invalid broker configuration")

@router.post("/", response_model=List[Dict])
async def get_candles(
    request: CandleRequest,
    broker: BrokerInterface = Depends(get_broker)
):
    """
    Get candle data with automatic gap filling
    
    - Queries TimescaleDB first
    - Detects missing data
    - Backfills from broker API if needed
    - Returns complete dataset
    """
    try:
        service = CandleService(broker)
        candles = await service.get_candles(
            request.instrument_token,
            request.from_date,
            request.to_date,
            request.interval
        )
        
        return candles
        
    except Exception as e:
        logger.error(f"Error fetching candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### app/api/instruments.py
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict
from app.database.connection import get_db_pool
from app.brokers.base import BrokerInterface
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

class InstrumentSubscribe(BaseModel):
    tokens: List[int]

async def get_broker() -> BrokerInterface:
    from app.config import get_settings
    settings = get_settings()
    
    if settings.BROKER == "kite":
        from app.brokers.kite import KiteBroker
        return KiteBroker()
    elif settings.BROKER == "fyers":
        from app.brokers.fyers import FyersBroker
        return FyersBroker()
    else:
        raise HTTPException(status_code=500, detail="Invalid broker configuration")

@router.get("/")
async def list_instruments():
    """List all instruments from database"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM instruments
                ORDER BY symbol
            """)
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error listing instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_instruments(broker: BrokerInterface = Depends(get_broker)):
    """
    Sync instrument master from broker
    
    - Fetches complete instrument list from broker
    - Updates database
    """
    try:
        instruments = await broker.get_instruments()
        
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Clear existing and insert new
            await conn.execute("TRUNCATE TABLE instruments")
            
            records = [
                (
                    i['token'],
                    i['symbol'],
                    i['exchange'],
                    i['segment'],
                    i.get('instrument_type'),
                    i.get('expiry'),
                    i.get('strike'),
                    i.get('option_type'),
                    i.get('lot_size')
                )
                for i in instruments
            ]
            
            await conn.executemany("""
                INSERT INTO instruments 
                (token, symbol, exchange, segment, instrument_type, 
                 expiry, strike, option_type, lot_size)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, records)
        
        logger.info(f"Synced {len(instruments)} instruments")
        return {"status": "success", "count": len(instruments)}
        
    except Exception as e:
        logger.error(f"Error syncing instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscribe")
async def subscribe_instruments(
    data: InstrumentSubscribe,
    broker: BrokerInterface = Depends(get_broker)
):
    """
    Subscribe to real-time tick data for instruments
    
    - Starts WebSocket connection
    - Begins tick ingestion
    """
    try:
        from app.main import get_ingestion_service
        ingestion_service = get_ingestion_service()
        
        # Connect WebSocket with callback to ingestion service
        await broker.connect_websocket(
            data.tokens,
            ingestion_service.handle_tick
        )
        
        return {
            "status": "subscribed",
            "tokens": data.tokens,
            "count": len(data.tokens)
        }
        
    except Exception as e:
        logger.error(f"Error subscribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### app/api/websocket.py
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
from app.utils.logger import get_logger
import asyncio

router = APIRouter()
logger = get_logger(__name__)

# Active WebSocket connections
active_connections: Set[WebSocket] = set()

@router.websocket("/ticks")
async def websocket_ticks(websocket: WebSocket):
    """
    WebSocket endpoint for real-time tick streaming to clients
    
    Note: This is for CLIENT connections (e.g., custom frontends)
    Grafana will query TimescaleDB directly
    """
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("WebSocket client disconnected")

async def broadcast_tick(tick_data: dict):
    """Broadcast tick to all connected WebSocket clients"""
    for connection in active_connections.copy():
        try:
            await connection.send_json(tick_data)
        except:
            active_connections.remove(connection)
```

### app/brokers/kite.py (Skeleton)
```python
from typing import List, Dict, Callable
from datetime import datetime
from app.brokers.base import BrokerInterface
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class KiteBroker(BrokerInterface):
    """
    Kite (Zerodha) API implementation
    
    TODO: Implement using KiteConnect library
    - pip install kiteconnect
    """
    
    def __init__(self):
        self.api_key = settings.KITE_API_KEY
        self.access_token = settings.KITE_ACCESS_TOKEN
        self.kite = None  # Initialize KiteConnect here
        self.kws = None   # Initialize KiteTicker here
    
    async def connect_websocket(
        self, 
        instruments: List[int], 
        callback: Callable
    ) -> None:
        """
        Connect to Kite WebSocket
        
        TODO: Implement WebSocket connection
        - Initialize KiteTicker
        - Subscribe to instruments
        - Call callback with each tick
        """
        logger.info(f"Connecting to Kite WebSocket for {len(instruments)} instruments")
        # Implementation here
        pass
    
    async def disconnect_websocket(self) -> None:
        """Disconnect from Kite WebSocket"""
        if self.kws:
            self.kws.close()
        logger.info("Disconnected from Kite WebSocket")
    
    async def fetch_historical_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "minute"
    ) -> List[Dict]:
        """
        Fetch historical data from Kite
        
        TODO: Implement using kite.historical_data()
        """
        logger.info(f"Fetching historical data for {instrument_token}")
        # Implementation here
        return []
    
    async def get_instruments(self) -> List[Dict]:
        """
        Fetch instrument master from Kite
        
        TODO: Implement using kite.instruments()
        """
        logger.info("Fetching instruments from Kite")
        # Implementation here
        return []
```

### app/brokers/fyers.py (Skeleton)
```python
from typing import List, Dict, Callable
from datetime import datetime
from app.brokers.base import BrokerInterface
from app.utils.logger import get_logger
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class FyersBroker(BrokerInterface):
    """
    Fyers API implementation
    
    TODO: Implement using Fyers API library
    """
    
    def __init__(self):
        self.app_id = settings.FYERS_APP_ID
        self.access_token = settings.FYERS_ACCESS_TOKEN
        self.fyers = None  # Initialize Fyers client here
    
    async def connect_websocket(
        self, 
        instruments: List[int], 
        callback: Callable
    ) -> None:
        """Connect to Fyers WebSocket"""
        logger.info(f"Connecting to Fyers WebSocket for {len(instruments)} instruments")
        # Implementation here
        pass
    
    async def disconnect_websocket(self) -> None:
        """Disconnect from Fyers WebSocket"""
        logger.info("Disconnected from Fyers WebSocket")
    
    async def fetch_historical_candles(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1"
    ) -> List[Dict]:
        """Fetch historical data from Fyers"""
        logger.info(f"Fetching historical data for {instrument_token}")
        # Implementation here
        return []
    
    async def get_instruments(self) -> List[Dict]:
        """Fetch instrument master from Fyers"""
        logger.info("Fetching instruments from Fyers")
        # Implementation here
        return []
```

### app/utils/logger.py
```python
import logging
import sys
from app.config import get_settings

settings = get_settings()

def setup_logger():
    """Configure application logging"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)
```

### app/utils/redis_client.py
```python
import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()
redis_client = None

async def get_redis():
    """Get Redis client"""
    global redis_client
    if not redis_client:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client
```

## Grafana Configuration

### grafana/provisioning/datasources/timescaledb.yml
```yaml
apiVersion: 1

datasources:
  - name: TimescaleDB
    type: postgres
    access: proxy
    url: timescaledb:5432
    database: trading_data
    user: trading_user
    secureJsonData:
      password: 'trading_secure_password_2024'
    jsonData:
      sslmode: 'disable'
      postgresVersion: 1500
      timescaledb: true
    editable: true
    isDefault: true
```

### grafana/provisioning/dashboards/dashboard.yml
```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### Sample Grafana Dashboard Query
```sql
-- Query for 5-minute candles (use in Grafana panel)
SELECT 
    bucket AS time,
    open,
    high,
    low,
    close,
    volume
FROM candles_5m
WHERE 
    instrument_token = 256265
    AND bucket >= NOW() - INTERVAL '1 day'
ORDER BY bucket
```

## Environment Variables

### .env.example
```bash
# Database
DATABASE_URL=postgresql://trading_user:trading_secure_password_2024@timescaledb:5432/trading_data

# Redis
REDIS_URL=redis://redis:6379

# Broker Selection (kite or fyers)
BROKER=kite

# Kite API Credentials
KITE_API_KEY=your_kite_api_key_here
KITE_ACCESS_TOKEN=your_kite_access_token_here

# Fyers API Credentials
FYERS_APP_ID=your_fyers_app_id_here
FYERS_ACCESS_TOKEN=your_fyers_access_token_here

# Application Settings
LOG_LEVEL=INFO
TICK_BUFFER_SIZE=1000
FLUSH_INTERVAL_SECONDS=1
```

## Development Workflow

### Initial Setup
```bash
# 1. Clone repository
git clone <your-repo-url>
cd trading-helper

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env with your broker credentials
nano .env

# 4. Start all services
docker-compose up -d

# 5. Check logs
docker-compose logs -f

# 6. Initialize database (schema.sql runs automatically)
# Verify: docker-compose exec timescaledb psql -U trading_user -d trading_data -c "\dt"

# 7. Access services
# - FastAPI Docs: http://localhost:8000/docs
# - Grafana: http://localhost:3000 (admin/admin)
# - TimescaleDB: localhost:5432
```

### Sync Instruments from Broker
```bash
# Sync instrument master
curl -X POST http://localhost:8000/api/instruments/sync

# Verify
curl http://localhost:8000/api/instruments | jq
```

### Subscribe to Real-Time Data
```bash
# Subscribe to specific instruments
curl -X POST http://localhost:8000/api/instruments/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "tokens": [256265, 738561, 5633]
  }'

# Monitor tick ingestion
docker-compose logs -f fastapi
```

### Query Candles (with auto-backfill)
```bash
# Get 5-minute candles for last 24 hours
curl -X POST http://localhost:8000/api/candles \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_token": 256265,
    "from_date": "2025-10-18T09:15:00Z",
    "to_date": "2025-10-19T15:30:00Z",
    "interval": "5m"
  }'
```

### Check TimescaleDB Data
```bash
# Connect to database
docker-compose exec timescaledb psql -U trading_user -d trading_data

# Check tick data
SELECT COUNT(*) FROM tick_data;

# Check 1-minute candles
SELECT * FROM candles_1m ORDER BY bucket DESC LIMIT 10;

# Check continuous aggregate refresh
SELECT * FROM timescaledb_information.continuous_aggregates;
```

## Production Deployment (AWS)

### Architecture for AWS
```
┌─────────────────┐
│   Route 53      │
└────────┬────────┘
         │
┌────────▼────────┐
│      ALB        │
└────────┬────────┘
         │
┌────────▼────────┐
│   ECS Fargate   │ (FastAPI containers)
└────┬───────┬────┘
     │       │
┌────▼───┐ ┌▼────────────┐
│  RDS   │ │ ElastiCache │
│ (PG+TS)│ │   (Redis)   │
└────────┘ └─────────────┘
```

### AWS Services Needed
- **ECS Fargate**: Run FastAPI containers (auto-scaling)
- **RDS PostgreSQL + TimescaleDB**: Managed database with Multi-AZ
- **ElastiCache Redis**: Managed cache cluster
- **Application Load Balancer**: Distribute traffic
- **CloudWatch**: Logging, metrics, alarms
- **S3**: Backup storage for historical data
- **VPC**: Network isolation
- **Secrets Manager**: Store API credentials

### Terraform/CloudFormation Setup
```hcl
# Example Terraform for RDS with TimescaleDB
resource "aws_db_instance" "timescaledb" {
  identifier           = "trading-timescaledb"
  engine              = "postgres"
  engine_version      = "15.4"
  instance_class      = "db.r6g.xlarge"
  allocated_storage   = 100
  storage_type        = "gp3"
  
  db_name  = "trading_data"
  username = "trading_user"
  password = var.db_password
  
  multi_az               = true
  backup_retention_period = 7
  
  # Install TimescaleDB extension after creation
  # Run: CREATE EXTENSION IF NOT EXISTS timescaledb;
}
```

### Scaling Considerations
- **Horizontal scaling**: 2-10 FastAPI containers based on load
- **Database**: Read replicas for Grafana queries
- **Partitioning**: TimescaleDB chunks by time (automatic)
- **Caching**: Redis for frequently accessed instruments
- **Monitoring**: CloudWatch alarms for latency, error rates

## Monitoring & Observability

### Health Checks
```python
# Add to app/main.py
@app.get("/health/db")
async def health_db():
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "component": "database"}
    except:
        return {"status": "unhealthy", "component": "database"}

@app.get("/health/redis")
async def health_redis():
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        return {"status": "healthy", "component": "redis"}
    except:
        return {"status": "unhealthy", "component": "redis"}
```

### Metrics to Track
- Tick ingestion rate (ticks/second)
- WebSocket connection status
- Buffer flush latency
- Database insert performance
- Continuous aggregate refresh lag
- API response times
- Error rates

## Troubleshooting

### Common Issues

**1. TimescaleDB continuous aggregates not updating**
```sql
-- Check refresh policies
SELECT * FROM timescaledb_information.job_stats;

-- Manual refresh
CALL refresh_continuous_aggregate('candles_1m', NULL, NULL);
```

**2. High tick data volume causing slowness**
```sql
-- Check chunk size
SELECT * FROM timescaledb_information.chunks WHERE hypertable_name = 'tick_data';

-- Adjust chunk interval if needed
SELECT set_chunk_time_interval('tick_data', INTERVAL '1 hour');
```

**3. WebSocket disconnections**
- Check broker API rate limits
- Implement exponential backoff reconnection
- Log all connection errors

**4. Missing data gaps**
```sql
-- Find gaps in tick data
SELECT 
    instrument_token,
    bucket,
    LEAD(bucket) OVER (PARTITION BY instrument_token ORDER BY bucket) - bucket AS gap
FROM candles_1m
WHERE gap > INTERVAL '1 minute'
LIMIT 100;
```

## Testing

### Unit Tests (Example)
```python
# tests/test_candle_service.py
import pytest
from app.services.candle_service import CandleService
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_find_gaps():
    service = CandleService(mock_broker)
    
    candles = [
        {'bucket': datetime(2025, 10, 19, 9, 15)},
        {'bucket': datetime(2025, 10, 19, 9, 16)},
        # Gap here
        {'bucket': datetime(2025, 10, 19, 9, 20)},
    ]
    
    gaps = service._find_gaps(
        candles,
        datetime(2025, 10, 19, 9, 15),
        datetime(2025, 10, 19, 9, 30),
        "1m"
    )
    
    assert len(gaps) > 0
```

## Performance Optimization

### Database Indexes
```sql
-- Additional indexes for common queries
CREATE INDEX idx_candles_1m_time_range 
    ON candles_1m (bucket) 
    WHERE bucket >= NOW() - INTERVAL '7 days';

-- Partial index for active trading hours
CREATE INDEX idx_tick_data_trading_hours 
    ON tick_data (time, instrument_token) 
    WHERE EXTRACT(HOUR FROM time) BETWEEN 9 AND 15;
```

### Query Optimization
```sql
-- Use time_bucket_gapfill for missing intervals
SELECT 
    time_bucket_gapfill('5 minutes', bucket) AS time,
    instrument_token,
    COALESCE(AVG(close), LAG(close) OVER (ORDER BY bucket)) AS close
FROM candles_1m
WHERE instrument_token = 256265
GROUP BY time, instrument_token
ORDER BY time;
```

### Connection Pooling
- FastAPI: 10-20 database connections
- Grafana: Separate read-only connection pool
- Use pgBouncer for connection pooling in production

## Security Considerations

### API Security
```python
# Add authentication middleware
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/api/protected")
async def protected_route(credentials: HTTPBearer = Depends(security)):
    # Validate token
    pass
```

### Database Security
- Use strong passwords
- Enable SSL for database connections
- Restrict database access to VPC only (production)
- Use IAM roles for RDS access (AWS)

### Environment Variables
- Never commit .env files
- Use AWS Secrets Manager in production
- Rotate credentials regularly

## Next Steps / Roadmap

### Phase 1: MVP (Week 1-2)
- [x] Setup Docker Compose
- [x] Create TimescaleDB schema
- [ ] Implement Kite broker WebSocket
- [ ] Test tick ingestion with 10 instruments
- [ ] Create basic Grafana dashboard
- [ ] Verify continuous aggregates working

### Phase 2: Core Features (Week 3-4)
- [ ] Implement gap detection and backfill
- [ ] Add Fyers broker support
- [ ] Handle WebSocket reconnections
- [ ] Add error handling and logging
- [ ] Performance testing with 500+ instruments
- [ ] Optimize database queries

### Phase 3: Production Ready (Week 5-6)
- [ ] Add authentication
- [ ] Implement monitoring/alerting
- [ ] Create comprehensive Grafana dashboards
- [ ] Add unit and integration tests
- [ ] Documentation
- [ ] AWS deployment scripts

### Phase 4: Advanced Features (Future)
- [ ] Custom indicators in TimescaleDB
- [ ] Pattern recognition
- [ ] Alert system (price/volume alerts)
- [ ] Export to CSV/Excel
- [ ] Mobile app integration
- [ ] Multi-user support

## FAQs

**Q: Why TimescaleDB over InfluxDB?**
A: TimescaleDB is better for multi-instrument tick data (high cardinality), has native SQL, better compression, and easier AWS migration.

**Q: Can I use this without Docker?**
A: Yes, but Docker Compose is recommended for local development. For production, use managed services (RDS, ElastiCache).

**Q: How much storage is needed?**
A: For 1000 instruments with tick-by-tick data during market hours (6.5 hours):
- Raw ticks: ~50GB/week (compressed to ~5GB)
- 1m candles: ~500MB/month
- Higher timeframes: negligible

**Q: Can this handle options chain (all strikes)?**
A: Yes, but be mindful of WebSocket subscription limits (usually 3000-5000 instruments per connection). Use multiple connections if needed.

**Q: How to backup data?**
A: TimescaleDB supports `pg_dump`. For AWS RDS, use automated snapshots. Continuous aggregates can be rebuilt from tick data if needed.

**Q: Real-time alerting?**
A: Add Grafana alerting rules or implement custom alert service that queries TimescaleDB views.

## Resources

### Documentation Links
- [TimescaleDB Docs](https://docs.timescale.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Kite Connect Docs](https://kite.trade/docs/connect/v3/)
- [Fyers API Docs](https://fyers.in/docs/)
- [Grafana Docs](https://grafana.com/docs/)

### Sample Queries Collection
```sql
-- Top gainers (1-day change)
SELECT 
    i.symbol,
    (c.close - c.open) / c.open * 100 AS change_pct,
    c.volume
FROM candles_1d c
JOIN instruments i ON i.token = c.instrument_token
WHERE c.bucket = time_bucket('1 day', NOW())
ORDER BY change_pct DESC
LIMIT 20;

-- Highest volume spikes (vs 5-day avg)
SELECT 
    i.symbol,
    c.volume,
    AVG(c.volume) OVER (
        PARTITION BY c.instrument_token 
        ORDER BY c.bucket 
        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
    ) AS avg_volume_5d,
    c.volume / NULLIF(AVG(c.volume) OVER (
        PARTITION BY c.instrument_token 
        ORDER BY c.bucket 
        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
    ), 0) AS volume_spike_ratio
FROM candles_1d c
JOIN instruments i ON i.token = c.instrument_token
WHERE c.bucket >= NOW() - INTERVAL '7 days'
ORDER BY volume_spike_ratio DESC
LIMIT 20;

-- Option chain analysis (highest OI)
SELECT 
    i.symbol,
    i.strike,
    i.option_type,
    c.open_interest,
    c.close AS ltp
FROM candles_1m c
JOIN instruments i ON i.token = c.instrument_token
WHERE 
    i.segment = 'OPT'
    AND i.expiry = '2025-10-24'
    AND c.bucket = (SELECT MAX(bucket) FROM candles_1m)
ORDER BY c.open_interest DESC
LIMIT 50;

-- Intraday VWAP
SELECT 
    bucket,
    instrument_token,
    close,
    SUM(close * volume) OVER w / NULLIF(SUM(volume) OVER w, 0) AS vwap
FROM candles_1m
WHERE 
    instrument_token = 256265
    AND bucket >= date_trunc('day', NOW())
WINDOW w AS (
    PARTITION BY instrument_token 
    ORDER BY bucket 
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
ORDER BY bucket;

-- Volatility (standard deviation of returns)
SELECT 
    instrument_token,
    STDDEV(
        (close - LAG(close) OVER (PARTITION BY instrument_token ORDER BY bucket)) 
        / NULLIF(LAG(close) OVER (PARTITION BY instrument_token ORDER BY bucket), 0)
    ) AS volatility
FROM candles_1d
WHERE bucket >= NOW() - INTERVAL '30 days'
GROUP BY instrument_token
ORDER BY volatility DESC;
```

## Appendix: Complete File Checklist

### Files You Need to Create

```
trading-helper/
├── docker-compose.yml ✓
├── .env ✓
├── .env.example ✓
├── .gitignore
├── Dockerfile ✓
├── requirements.txt ✓
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py ✓
│   ├── config.py ✓
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── instruments.py ✓
│   │   ├── candles.py ✓
│   │   └── websocket.py ✓
│   │
│   ├── brokers/
│   │   ├── __init__.py
│   │   ├── base.py ✓
│   │   ├── kite.py ✓ (skeleton - needs implementation)
│   │   └── fyers.py ✓ (skeleton - needs implementation)
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py ✓
│   │   ├── models.py (optional - using raw SQL)
│   │   └── schema.sql ✓ (CRITICAL - all continuous aggregates)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_ingestion.py ✓
│   │   └── candle_service.py ✓
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py ✓
│       └── redis_client.py ✓
│
├── grafana/
│   ├── dashboards/
│   │   └── market_overview.json (to be created in Grafana UI)
│   └── provisioning/
│       ├── datasources/
│       │   └── timescaledb.yml ✓
│       └── dashboards/
│           └── dashboard.yml ✓
│
├── scripts/
│   ├── init_db.py (optional - schema.sql runs automatically)
│   └── seed_instruments.py (optional - use /sync endpoint)
│
└── tests/
    ├── __init__.py
    ├── test_candle_service.py
    └── test_data_ingestion.py
```

### .gitignore
```gitignore
# Environment
.env
.env.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Docker
docker-compose.override.yml

# Data
*.db
*.sqlite

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db
```

## Implementation Priority Order

### 1. Start Here (Core Infrastructure)
```bash
# Create these files first:
1. docker-compose.yml
2. .env
3. Dockerfile
4. requirements.txt
5. app/database/schema.sql (MOST IMPORTANT - has all continuous aggregates)
6. app/config.py
7. app/main.py
```

### 2. Database Layer
```bash
8. app/database/connection.py
9. app/utils/logger.py
10. app/utils/redis_client.py
```

### 3. Broker Integration (Choose ONE first)
```bash
# If starting with Kite:
11. app/brokers/base.py
12. app/brokers/kite.py (implement WebSocket + historical API)

# OR if starting with Fyers:
11. app/brokers/base.py
12. app/brokers/fyers.py (implement WebSocket + historical API)
```

### 4. Data Services
```bash
13. app/services/data_ingestion.py
14. app/services/candle_service.py
```

### 5. API Endpoints
```bash
15. app/api/instruments.py
16. app/api/candles.py
17. app/api/websocket.py
```

### 6. Grafana Setup
```bash
18. grafana/provisioning/datasources/timescaledb.yml
19. grafana/provisioning/dashboards/dashboard.yml
20. Create dashboards in Grafana UI, export to JSON
```

### 7. Testing & Validation
```bash
# Test the complete flow:
1. docker-compose up -d
2. Check all services healthy
3. Sync instruments: POST /api/instruments/sync
4. Subscribe to ticks: POST /api/instruments/subscribe
5. Monitor logs for tick ingestion
6. Query database to verify continuous aggregates
7. Create Grafana dashboard
8. Test gap filling: Query old data via /api/candles
```

## Critical Implementation Notes for Cursor/Claude Code

### 🔴 MUST IMPLEMENT (Priority 1)
1. **schema.sql** - Contains ALL continuous aggregates (1m, 5m, 15m, 1h, 1d)
2. **Broker WebSocket** - Either Kite or Fyers real-time connection
3. **data_ingestion.py** - Buffering and batch insert logic
4. **candle_service.py** - Gap detection and backfill

### 🟡 SHOULD IMPLEMENT (Priority 2)
1. Error handling and reconnection logic for WebSocket
2. Proper logging throughout
3. Health check endpoints
4. Grafana datasource provisioning

### 🟢 NICE TO HAVE (Priority 3)
1. Unit tests
2. WebSocket endpoint for clients
3. Advanced Grafana dashboards
4. Metrics and monitoring

## Sample Grafana Dashboard Panels

### Panel 1: Live Price Chart
```sql
-- Query for candlestick chart
SELECT 
    bucket AS "time",
    open,
    high,
    low,
    close
FROM candles_1m
WHERE 
    instrument_token = $instrument
    AND bucket >= $__timeFrom()
    AND bucket <= $__timeTo()
ORDER BY bucket
```

**Visualization**: Candlestick chart
**Variables**: 
- `$instrument` - Multi-select dropdown of instruments

### Panel 2: Volume
```sql
SELECT 
    bucket AS "time",
    volume
FROM candles_1m
WHERE 
    instrument_token = $instrument
    AND bucket >= $__timeFrom()
    AND bucket <= $__timeTo()
ORDER BY bucket
```

**Visualization**: Bar chart

### Panel 3: Open Interest
```sql
SELECT 
    bucket AS "time",
    open_interest
FROM candles_1m
WHERE 
    instrument_token = $instrument
    AND bucket >= $__timeFrom()
    AND bucket <= $__timeTo()
ORDER BY bucket
```

**Visualization**: Line chart

### Panel 4: Market Depth (Latest Tick)
```sql
SELECT 
    bid_price,
    bid_qty,
    ask_price,
    ask_qty,
    ltp
FROM tick_data
WHERE instrument_token = $instrument
ORDER BY time DESC
LIMIT 1
```

**Visualization**: Stat panel

### Panel 5: Top Movers
```sql
SELECT 
    i.symbol,
    c.close,
    (c.close - c_prev.close) / c_prev.close * 100 AS change_pct
FROM candles_1m c
JOIN instruments i ON i.token = c.instrument_token
LEFT JOIN candles_1m c_prev ON 
    c_prev.instrument_token = c.instrument_token
    AND c_prev.bucket = c.bucket - INTERVAL '1 minute'
WHERE 
    c.bucket = (SELECT MAX(bucket) FROM candles_1m)
    AND i.segment = 'CASH'
ORDER BY ABS(change_pct) DESC
LIMIT 10
```

**Visualization**: Table

## Final Checklist Before Going Live

- [ ] All environment variables set in .env
- [ ] Broker API credentials validated
- [ ] TimescaleDB schema created successfully
- [ ] All continuous aggregates created
- [ ] Compression and retention policies active
- [ ] Instrument master synced
- [ ] WebSocket connection working
- [ ] Tick ingestion verified (check database)
- [ ] Continuous aggregates updating (check candles_1m)
- [ ] Grafana datasource connected
- [ ] At least one dashboard created
- [ ] Gap filling tested with historical query
- [ ] Logs configured and readable
- [ ] Health checks responding
- [ ] Docker containers stable (no restarts)

## Support & Troubleshooting Commands

```bash
# View all logs
docker-compose logs -f

# Check database
docker-compose exec timescaledb psql -U trading_user -d trading_data

# Restart specific service
docker-compose restart fastapi

# Check continuous aggregate jobs
docker-compose exec timescaledb psql -U trading_user -d trading_data -c "
SELECT * FROM timescaledb_information.job_stats 
WHERE job_id IN (
    SELECT job_id FROM timescaledb_information.continuous_aggregates
);
"

# Manual refresh of aggregate
docker-compose exec timescaledb psql -U trading_user -d trading_data -c "
CALL refresh_continuous_aggregate('candles_1m', NULL, NULL);
"

# Check disk usage
docker-compose exec timescaledb psql -U trading_user -d trading_data -c "
SELECT 
    pg_size_pretty(pg_database_size('trading_data')) AS db_size,
    pg_size_pretty(pg_total_relation_size('tick_data')) AS tick_data_size,
    pg_size_pretty(pg_total_relation_size('candles_1m')) AS candles_1m_size;
"

# Clean up old data manually (if needed)
docker-compose exec timescaledb psql -U trading_user -d trading_data -c "
SELECT drop_chunks('tick_data', INTERVAL '30 days');
"
```

---

## Summary for Cursor/Claude Code

**This specification contains everything needed to build a production-ready trading data system:**

1. ✅ **Complete database schema** with TimescaleDB continuous aggregates for multi-timeframe support
2. ✅ **FastAPI structure** with all necessary endpoints and services
3. ✅ **Broker abstraction** for both Kite and Fyers (skeletons provided)
4. ✅ **Docker Compose** setup for local development
5. ✅ **Grafana integration** with provisioning and sample queries
6. ✅ **Smart gap filling** - automatic historical data backfill
7. ✅ **Zero processing in FastAPI** - all aggregation in database
8. ✅ **Production roadmap** for AWS deployment

**Key Architecture Decision:**
- Store tick data during market hours
- TimescaleDB automatically creates 1m, 5m, 15m, 1h, 1d candles
- Grafana queries appropriate view based on timeframe
- Gap filling happens on-demand when missing data detected

**Start by implementing in this order:**
1. Docker infrastructure
2. Database schema (schema.sql)
3. One broker integration (Kite or Fyers)
4. Data ingestion service
5. API endpoints
6. Grafana dashboards

Good luck! 🚀
