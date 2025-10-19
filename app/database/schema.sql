-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Instruments master table
CREATE TABLE IF NOT EXISTS instruments (
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

CREATE INDEX IF NOT EXISTS idx_instruments_token ON instruments(token);
CREATE INDEX IF NOT EXISTS idx_instruments_symbol ON instruments(symbol);
CREATE INDEX IF NOT EXISTS idx_instruments_exchange ON instruments(exchange);

-- Backfill tracking table
CREATE TABLE IF NOT EXISTS backfill_status (
    instrument_token INTEGER PRIMARY KEY,
    last_backfilled_date TIMESTAMPTZ NOT NULL,
    last_backfilled_from TIMESTAMPTZ NOT NULL,
    last_backfilled_to TIMESTAMPTZ NOT NULL,
    candle_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backfill_status_date ON backfill_status(last_backfilled_date DESC);

-- Tick data table (will be converted to hypertable)
CREATE TABLE IF NOT EXISTS tick_data (
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

-- Convert to hypertable
SELECT create_hypertable('tick_data', 'time', if_not_exists => TRUE);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_tick_data_instrument_time 
    ON tick_data (instrument_token, time DESC);

-- Compression policy (compress after 1 day)
ALTER TABLE tick_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'instrument_token'
);

-- Add compression policy (compress data older than 1 day)
SELECT add_compression_policy('tick_data', INTERVAL '1 day', if_not_exists => TRUE);

-- Retention policy (drop data older than 7 days)
SELECT add_retention_policy('tick_data', INTERVAL '7 days', if_not_exists => TRUE);

-- 1-minute candles (continuous aggregate)
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1m
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
CREATE INDEX IF NOT EXISTS idx_candles_1m_instrument_bucket 
    ON candles_1m (instrument_token, bucket DESC);

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('candles_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

-- Retention policy (drop data older than 30 days)
SELECT add_retention_policy('candles_1m', INTERVAL '30 days', if_not_exists => TRUE);

-- 5-minute candles (continuous aggregate)
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_5m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS bucket,
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
CREATE INDEX IF NOT EXISTS idx_candles_5m_instrument_bucket 
    ON candles_5m (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_5m',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

-- Retention policy (drop data older than 90 days)
SELECT add_retention_policy('candles_5m', INTERVAL '90 days', if_not_exists => TRUE);

-- 15-minute candles (continuous aggregate)
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_15m
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('15 minutes', time) AS bucket,
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
CREATE INDEX IF NOT EXISTS idx_candles_15m_instrument_bucket 
    ON candles_15m (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_15m',
    start_offset => INTERVAL '6 hours',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- Retention policy (drop data older than 6 months)
SELECT add_retention_policy('candles_15m', INTERVAL '6 months', if_not_exists => TRUE);

-- ============================================
-- CONTINUOUS AGGREGATE: 1-HOUR CANDLES
-- ============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1h
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

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_candles_1h_instrument_bucket 
    ON candles_1h (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_1h',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- Retention policy (drop data older than 1 year)
SELECT add_retention_policy('candles_1h', INTERVAL '1 year', if_not_exists => TRUE);

-- ============================================
-- CONTINUOUS AGGREGATE: 1-DAY CANDLES
-- ============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1d
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

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_candles_1d_instrument_bucket 
    ON candles_1d (instrument_token, bucket DESC);

SELECT add_continuous_aggregate_policy('candles_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- No retention policy for daily candles (keep forever)

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON TABLE tick_data IS 'Raw tick-by-tick data from broker WebSocket. Compressed after 1 day, deleted after 7 days.';
COMMENT ON MATERIALIZED VIEW candles_1m IS '1-minute OHLCV candles. Auto-aggregated from tick_data. Retained for 30 days.';
COMMENT ON MATERIALIZED VIEW candles_5m IS '5-minute OHLCV candles. Auto-aggregated from candles_1m. Retained for 90 days.';
COMMENT ON MATERIALIZED VIEW candles_15m IS '15-minute OHLCV candles. Auto-aggregated from candles_5m. Retained for 6 months.';
COMMENT ON MATERIALIZED VIEW candles_1h IS '1-hour OHLCV candles. Auto-aggregated from candles_15m. Retained for 1 year.';
COMMENT ON MATERIALIZED VIEW candles_1d IS '1-day OHLCV candles. Auto-aggregated from candles_1h. Retained indefinitely.';

-- Subscribed instruments (tracking which instruments to stream)
CREATE TABLE IF NOT EXISTS subscribed_instruments (
    instrument_token INTEGER PRIMARY KEY,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

