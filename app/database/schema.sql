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

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('candles_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

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

SELECT add_continuous_aggregate_policy('candles_5m',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

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

SELECT add_continuous_aggregate_policy('candles_15m',
    start_offset => INTERVAL '6 hours',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- Subscribed instruments (tracking which instruments to stream)
CREATE TABLE IF NOT EXISTS subscribed_instruments (
    instrument_token INTEGER PRIMARY KEY,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

