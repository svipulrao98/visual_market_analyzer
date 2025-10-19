# Quick Start Guide

Get the Trading Helper System up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11 (if running locally without Docker)
- Kite or Fyers API credentials

## Step 1: Configure Credentials

Edit the `env.example` file and add your broker credentials:

```bash
# For Kite
BROKER=kite
KITE_API_KEY=your_actual_api_key
KITE_ACCESS_TOKEN=your_actual_access_token

# OR for Fyers
BROKER=fyers
FYERS_APP_ID=your_actual_app_id
FYERS_ACCESS_TOKEN=your_actual_access_token
```

Then copy it to `.env`:
```bash
cp env.example .env
```

## Step 2: Start Services

```bash
# Start all services
docker-compose up -d

# Wait for services to be ready (about 30 seconds)
sleep 30

# Initialize database
docker-compose exec fastapi python scripts/init_db.py
```

Or use the automated setup script:
```bash
./setup.sh
```

## Step 3: Sync Instruments

Fetch instrument master from your broker:

```bash
docker-compose exec fastapi python scripts/seed_instruments.py
```

This will download and store all available instruments (stocks, futures, options) in the database.

## Step 4: Subscribe to Instruments

Subscribe to specific instruments for real-time data:

```bash
# Example: Subscribe to NIFTY and BANKNIFTY indices
docker-compose exec fastapi python scripts/subscribe_instruments.py 256265 260105
```

Or use the API:

```bash
curl -X POST http://localhost:8000/api/instruments/subscribe \
  -H "Content-Type: application/json" \
  -d '{"tokens": [256265, 260105]}'
```

## Step 5: Start Streaming

Start the broker WebSocket connection:

```bash
curl -X POST http://localhost:8000/api/ws/start
```

## Step 6: View Data

### Option A: Grafana Dashboard

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to Dashboards → Market Overview
4. Enter instrument token in the variable field
5. View real-time data!

### Option B: API

Get latest candles:
```bash
curl "http://localhost:8000/api/historical/candles?instrument_token=256265&interval=1m&from_date=2024-01-01&to_date=2024-12-31"
```

### Option C: WebSocket

Connect to real-time stream:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/ticks');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# FastAPI only
docker-compose logs -f fastapi

# Database only
docker-compose logs -f timescaledb
```

### Check Status
```bash
# Service status
docker-compose ps

# API health
curl http://localhost:8000/health

# Streaming status
curl http://localhost:8000/api/ws/status

# Subscribed instruments
curl http://localhost:8000/api/instruments/subscriptions/list
```

### Database Access
```bash
# Connect to database
docker-compose exec timescaledb psql -U trading_user -d trading_data

# Check data
docker-compose exec timescaledb psql -U trading_user -d trading_data \
  -c "SELECT COUNT(*) FROM tick_data;"

# View latest ticks
docker-compose exec timescaledb psql -U trading_user -d trading_data \
  -c "SELECT * FROM tick_data ORDER BY time DESC LIMIT 10;"
```

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v
```

## Finding Instrument Tokens

### Kite
```bash
# Search for instruments
curl "http://localhost:8000/api/instruments/search?q=NIFTY"

# Common tokens:
# NIFTY 50: 256265
# BANKNIFTY: 260105
# SENSEX: 265
```

### Fyers
```bash
# Search in database after syncing
curl "http://localhost:8000/api/instruments/search?q=NIFTY"
```

## Troubleshooting

### "Connection refused" errors
Wait longer for services to start (try 60 seconds), then retry.

### No data in Grafana
1. Verify instruments are subscribed
2. Check WebSocket is connected
3. Wait a few minutes for data to accumulate

### WebSocket not connecting
1. Check broker credentials in `.env`
2. Ensure access token is valid
3. Check logs: `docker-compose logs -f fastapi`

### Database errors
```bash
# Restart database
docker-compose restart timescaledb

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

## Next Steps

- Explore the API docs: http://localhost:8000/docs
- Customize Grafana dashboards
- Backfill historical data
- Set up alerts and notifications
- Build your trading strategies!

## Support

For detailed documentation, see [README.md](README.md)

For API documentation, visit http://localhost:8000/docs

