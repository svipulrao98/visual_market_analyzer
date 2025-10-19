# Trading Helper System

A real-time trading data ingestion and visualization system supporting Kite and Fyers APIs. The system captures tick-by-tick market data, stores historical information, and provides Grafana dashboards for analysis.

## Features

- **Real-time Data Streaming**: WebSocket-based tick-by-tick data ingestion from Kite/Fyers
- **Time-Series Database**: TimescaleDB for efficient storage and querying of market data
- **Automatic Aggregation**: Continuous aggregates for 1m, 5m, and 15m candles
- **Data Compression**: Automatic compression of data older than 1 day
- **Retention Policy**: Automatic cleanup of data older than 7 days
- **RESTful API**: FastAPI-based API for data access and management
- **Real-time Dashboard**: Grafana dashboards for market visualization
- **Broker Abstraction**: Easy switching between Kite and Fyers brokers

## Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Database**: TimescaleDB (PostgreSQL 15 + TimescaleDB extension)
- **Cache/Queue**: Redis 7.x
- **Visualization**: Grafana 10.x
- **Orchestration**: Docker Compose

## Project Structure

```
visual_market_analyzer/
├── app/
│   ├── api/              # API endpoints
│   ├── brokers/          # Broker implementations (Kite, Fyers)
│   ├── database/         # Database models and queries
│   ├── services/         # Business logic services
│   ├── utils/            # Utility functions
│   ├── config.py         # Configuration management
│   └── main.py           # FastAPI application
├── grafana/
│   ├── dashboards/       # Grafana dashboard JSON files
│   └── provisioning/     # Grafana auto-provisioning
├── scripts/              # Utility scripts
├── docker-compose.yml    # Docker services configuration
├── Dockerfile            # FastAPI container
└── requirements.txt      # Python dependencies
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11 (for local development)
- Kite or Fyers API credentials

### Installation

1. **Clone the repository**
   ```bash
   cd visual_market_analyzer
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` file with your credentials**
   ```bash
   # Set your broker (kite or fyers)
   BROKER=kite
   
   # Add your Kite API credentials
   KITE_API_KEY=your_api_key_here
   KITE_ACCESS_TOKEN=your_access_token_here
   
   # Or Fyers API credentials
   FYERS_APP_ID=your_app_id_here
   FYERS_ACCESS_TOKEN=your_access_token_here
   ```

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Initialize database**
   ```bash
   docker-compose exec fastapi python scripts/init_db.py
   ```

6. **Seed instruments from broker**
   ```bash
   docker-compose exec fastapi python scripts/seed_instruments.py
   ```

7. **Subscribe to instruments for streaming**
   ```bash
   docker-compose exec fastapi python scripts/subscribe_instruments.py 256265 260105
   ```

### Access Services

- **FastAPI Documentation**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **TimescaleDB**: localhost:5432
- **Redis**: localhost:6379

## Usage

### API Endpoints

#### Instruments
- `GET /api/instruments` - List all instruments
- `GET /api/instruments/search?q=NIFTY` - Search instruments
- `GET /api/instruments/{token}` - Get instrument details
- `POST /api/instruments/sync` - Sync instruments from broker
- `POST /api/instruments/subscribe` - Subscribe to instruments
- `GET /api/instruments/subscriptions/list` - List subscribed instruments

#### Historical Data
- `POST /api/historical/backfill` - Backfill historical data
- `GET /api/historical/candles` - Get candle data
- `GET /api/historical/ticks` - Get raw tick data

#### WebSocket
- `WS /api/ws/ticks` - Real-time tick stream
- `POST /api/ws/start` - Start broker WebSocket
- `POST /api/ws/stop` - Stop broker WebSocket
- `GET /api/ws/status` - Get streaming status

### Examples

#### Subscribe to instruments via API
```bash
curl -X POST http://localhost:8000/api/instruments/subscribe \
  -H "Content-Type: application/json" \
  -d '{"tokens": [256265, 260105]}'
```

#### Backfill historical data
```bash
curl -X POST http://localhost:8000/api/historical/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_token": 256265,
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "interval": "1m"
  }'
```

#### Get candle data
```bash
curl "http://localhost:8000/api/historical/candles?instrument_token=256265&interval=5m&from_date=2024-01-01&to_date=2024-01-31"
```

### WebSocket Connection

Connect to real-time tick stream:

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/ticks');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Tick data:', data);
};

// Send ping to keep connection alive
setInterval(() => {
  ws.send(JSON.stringify({ command: 'ping' }));
}, 30000);
```

## Database Schema

### Tables

- **instruments**: Master table of all tradeable instruments
- **tick_data**: Hypertable for real-time tick data (auto-compressed after 1 day, deleted after 7 days)
- **candles_1m**: Continuous aggregate for 1-minute candles
- **candles_5m**: Continuous aggregate for 5-minute candles
- **candles_15m**: Continuous aggregate for 15-minute candles
- **subscribed_instruments**: Tracks subscribed instruments for streaming

### Data Retention

- Tick data: 7 days (configurable)
- Compressed data: 1 day+ (compressed but queryable)
- Candles: Indefinite (aggregated views)

## Configuration

All configuration is managed through environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379

# Broker
BROKER=kite  # or fyers

# API Credentials
KITE_API_KEY=your_key
KITE_ACCESS_TOKEN=your_token

# Application Settings
LOG_LEVEL=INFO
TICK_BUFFER_SIZE=1000
FLUSH_INTERVAL_SECONDS=1
```

## Development

### Local Development Setup

1. **Ensure Python 3.11 is installed**
   ```bash
   python --version  # Should show Python 3.11.x
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create virtual environment (recommended)**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Start infrastructure services only**
   ```bash
   docker-compose up -d timescaledb redis grafana
   ```

5. **Run FastAPI locally**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Running Tests

```bash
# Coming soon
pytest
```

## Monitoring

### Grafana Dashboards

Access Grafana at http://localhost:3000 and explore:

- **Market Overview**: Real-time price charts, volume, and open interest
- Custom dashboards for specific instruments

### Logs

View application logs:
```bash
docker-compose logs -f fastapi
```

View all service logs:
```bash
docker-compose logs -f
```

## Troubleshooting

### Database Connection Issues

```bash
# Check database status
docker-compose ps timescaledb

# Verify database connection
docker-compose exec timescaledb psql -U trading_user -d trading_data
```

### WebSocket Connection Issues

```bash
# Check broker connection status
curl http://localhost:8000/api/ws/status

# View WebSocket logs
docker-compose logs -f fastapi | grep -i websocket
```

### Data Not Showing in Grafana

1. Verify data exists in database:
   ```bash
   docker-compose exec timescaledb psql -U trading_user -d trading_data \
     -c "SELECT COUNT(*) FROM tick_data;"
   ```

2. Check subscribed instruments:
   ```bash
   curl http://localhost:8000/api/instruments/subscriptions/list
   ```

3. Verify continuous aggregates are refreshing:
   ```bash
   docker-compose exec timescaledb psql -U trading_user -d trading_data \
     -c "SELECT * FROM timescaledb_information.continuous_aggregates;"
   ```

## Performance Optimization

### For High-Frequency Data

1. Increase buffer size in `.env`:
   ```bash
   TICK_BUFFER_SIZE=5000
   ```

2. Adjust flush interval:
   ```bash
   FLUSH_INTERVAL_SECONDS=2
   ```

3. Scale database connections:
   - Modify `app/database/connection.py`
   - Increase `max_size` in connection pool

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify your license here]

## Support

For issues and questions:
- Create an issue on GitHub
- Check logs for error messages
- Review API documentation at http://localhost:8000/docs

## Roadmap

- [ ] Add authentication and authorization
- [ ] Implement strategy backtesting
- [ ] Add alert system for price/volume triggers
- [ ] Support for more brokers (Zerodha, Upstox, etc.)
- [ ] Mobile app for monitoring
- [ ] Machine learning for pattern recognition
- [ ] AWS deployment scripts
- [ ] Automated testing suite

## Acknowledgments

- [Kite Connect](https://kite.trade/)
- [Fyers API](https://fyers.in/)
- [TimescaleDB](https://www.timescale.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Grafana](https://grafana.com/)

