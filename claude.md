# Trading Helper System - Technical Specification

## Project Overview
A real-time trading data ingestion and visualization system supporting Kite and Fyers APIs. The system captures tick-by-tick market data, stores historical information, and provides Grafana dashboards for analysis.

## Tech Stack
- **Backend**: FastAPI (Python 3.11)
- **Database**: TimescaleDB (PostgreSQL 15 + TimescaleDB extension)
- **Cache/Queue**: Redis 7.x
- **Visualization**: Grafana 10.x
- **Orchestration**: Docker Compose
- **Deployment**: Local (future: AWS)

## System Architecture

```
┌─────────────────┐
│  Kite/Fyers WS  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────┐
│   FastAPI App   │◄────►│  Redis   │
└────────┬────────┘      └──────────┘
         │
         ▼
┌─────────────────┐
│  TimescaleDB    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Grafana      │
└─────────────────┘
```

## Core Requirements

### 1. Data Sources
- **Kite API**: WebSocket for real-time tick data + Historical REST API
- **Fyers API**: WebSocket for real-time tick data + Historical REST API
- Support switching between brokers via configuration

### 2. Data Types
- **Instruments**: NSE F&O (Index futures/options), Cash stocks, Stock futures
- **Real-time**: Tick-by-tick data (price, volume, OI, timestamp)
- **Historical**: 1-minute candles (OHLCV + OI)
- **Retention**: Last 7 days of tick data

### 3. Data Storage
- **Tick Data**: High-frequency inserts (~1000s per second during market hours)
- **Aggregated Data**: 1-minute candles auto-generated from ticks
- **Compression**: Automatic compression after 1 day
- **Cleanup**: Auto-delete tick data older than 7 days

### 4. Performance Targets
- Handle 500-1000 instruments simultaneously
- Sub-second latency for tick ingestion
- Support single user, multiple browser tabs
- Zero data loss during WebSocket reconnections

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
│   │   ├── historical.py       # Historical data backfill
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
│   │   └── schema.sql          # TimescaleDB schema
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_ingestion.py  # Real-time data handler
│   │   ├── historical.py       # Historical data fetcher
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

### Services Definition
```yaml
# docker-compose.yml
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: trading_data
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: <secure_password>
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
      - ./app/database/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  fastapi:
    build: .
    environment:
      DATABASE_URL: postgresql://trading_user:<password>@timescaledb:5432/trading_data
      REDIS_URL: redis://redis:6379
      BROKER: kite  # or fyers
      KITE_API_KEY: ${KITE_API_KEY}
      KITE_ACCESS_TOKEN: ${KITE_ACCESS_TOKEN}
    depends_on:
      - timescaledb
      - redis
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    ports:
      - "3000:3000"
    depends_on:
      - timescaledb

volumes:
  timescaledb_data:
  redis_data:
  grafana_data:
```

## Database Schema

### TimescaleDB Tables

```sql
-- Instruments master table
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

-- Tick data (hypertable)
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

SELECT create_hypertable('tick_data', 'time');

-- Create index for faster queries
CREATE INDEX idx_tick_data_instrument_time 
    ON tick_data (instrument_token, time DESC);

-- Compression policy (compress after 1 day)
ALTER TABLE tick_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_token'
);

SELECT add_compression_policy('tick_data', INTERVAL '1 day');

-- Retention policy (drop after 7 days)
SELECT add_retention_policy('tick_data', INTERVAL '7 days');

-- 1-minute candles (continuous aggregate)
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

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('candles_1m',
    start_offset => INTERVAL '2 minutes',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

## FastAPI Implementation

### Main Application Structure

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import instruments, historical, websocket
from app.database.connection import init_db
from app.utils.logger import setup_logger

app = FastAPI(title="Trading Helper API")

# CORS for Grafana
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()
    setup_logger()

# Include routers
app.include_router(instruments.router, prefix="/api/instruments", tags=["instruments"])
app.include_router(historical.router, prefix="/api/historical", tags=["historical"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### Broker Interface

```python
# app/brokers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Callable

class BrokerInterface(ABC):
    
    @abstractmethod
    async def connect_websocket(self, instruments: List[int], callback: Callable):
        """Connect to broker WebSocket and stream tick data"""
        pass
    
    @abstractmethod
    async def fetch_historical(self, instrument: int, from_date: str, to_date: str, interval: str):
        """Fetch historical candle data"""
        pass
    
    @abstractmethod
    async def get_instruments(self) -> List[Dict]:
        """Fetch instrument master list"""
        pass
```

### Data Ingestion Service

```python
# app/services/data_ingestion.py
import asyncio
from datetime import datetime
from app.database.connection import get_db_pool
from app.utils.redis_client import get_redis

class DataIngestionService:
    
    def __init__(self):
        self.buffer = []
        self.buffer_size = 1000
        self.flush_interval = 1  # seconds
    
    async def handle_tick(self, tick_data: dict):
        """Buffer incoming tick data and batch insert"""
        self.buffer.append(tick_data)
        
        if len(self.buffer) >= self.buffer_size:
            await self.flush_buffer()
    
    async def flush_buffer(self):
        """Bulk insert tick data to TimescaleDB"""
        if not self.buffer:
            return
        
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO tick_data 
                (time, instrument_token, ltp, volume, open_interest, 
                 bid_price, ask_price, bid_qty, ask_qty)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, self.buffer)
        
        self.buffer.clear()
    
    async def start_flush_loop(self):
        """Periodically flush buffer"""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush_buffer()
```

## API Endpoints

### Instrument Management
```
GET  /api/instruments          - List all instruments
POST /api/instruments/sync     - Sync instruments from broker
GET  /api/instruments/{token}  - Get instrument details
POST /api/instruments/subscribe - Subscribe to instruments for real-time data
```

### Historical Data
```
POST /api/historical/backfill  - Backfill historical data
GET  /api/historical/candles   - Query historical candles
```

### WebSocket
```
WS /api/ws/ticks              - Real-time tick stream for subscribed instruments
```

## Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://trading_user:password@localhost:5432/trading_data

# Redis
REDIS_URL=redis://localhost:6379

# Broker (kite or fyers)
BROKER=kite

# Kite API
KITE_API_KEY=your_api_key
KITE_ACCESS_TOKEN=your_access_token

# Fyers API
FYERS_APP_ID=your_app_id
FYERS_ACCESS_TOKEN=your_access_token

# Application
LOG_LEVEL=INFO
TICK_BUFFER_SIZE=1000
FLUSH_INTERVAL_SECONDS=1
```

## Grafana Dashboard Requirements

### Default Dashboard Panels
1. **Market Overview**
   - Current price, change %, volume for watchlist instruments
   
2. **Price Chart**
   - Candlestick chart with volume overlay
   - Selectable timeframes (1m, 5m, 15m, 1h)
   
3. **Order Book Depth**
   - Real-time bid/ask spread
   
4. **Open Interest Analysis**
   - OI change percentage
   - OI vs Price correlation

5. **System Health**
   - WebSocket connection status
   - Data ingestion rate
   - Database size

## Development Workflow

### Initial Setup
```bash
# 1. Clone and setup
git clone <repo>
cd trading-helper
cp .env.example .env
# Edit .env with your credentials

# 2. Start services
docker-compose up -d

# 3. Initialize database
docker-compose exec fastapi python scripts/init_db.py

# 4. Seed instruments
docker-compose exec fastapi python scripts/seed_instruments.py

# 5. Access services
# FastAPI: http://localhost:8000/docs
# Grafana: http://localhost:3000 (admin/admin)
```

### Testing WebSocket Connection
```bash
# Subscribe to instruments
curl -X POST http://localhost:8000/api/instruments/subscribe \
  -H "Content-Type: application/json" \
  -d '{"tokens": [256265, 738561]}'

# Monitor logs
docker-compose logs -f fastapi
```

## Production Considerations (Future AWS Deployment)

### AWS Architecture
- **ECS Fargate**: Run FastAPI containers
- **RDS PostgreSQL + TimescaleDB**: Managed database
- **ElastiCache Redis**: Managed cache
- **ALB**: Load balancer for FastAPI
- **CloudWatch**: Logging and monitoring
- **S3**: Backup historical data

### Scaling Strategies
- Horizontal scaling of FastAPI workers
- Read replicas for Grafana queries
- TimescaleDB partitioning optimization
- Redis cluster for high availability

## Open Questions to Address

1. **Broker Priority**: Start with Kite or Fyers implementation first?
2. **Instrument Count**: Exact number of instruments to track?
3. **Data Retention**: Delete old ticks or compress to 1m candles only?
4. **Authentication**: Need API authentication for FastAPI endpoints?
5. **Monitoring**: Need Prometheus metrics export?

## Next Steps

1. Implement base FastAPI structure with health check
2. Setup Docker Compose with all services
3. Create TimescaleDB schema and hypertables
4. Implement one broker (Kite or Fyers) WebSocket connector
5. Build data ingestion service with buffering
6. Create basic Grafana dashboard
7. Add historical data backfill endpoint
8. Implement second broker
9. Add error handling and reconnection logic
10. Performance testing and optimization

---

**Note**: This specification is designed for iterative development. Start with MVP (real-time tick ingestion + basic visualization), then add features incrementally.