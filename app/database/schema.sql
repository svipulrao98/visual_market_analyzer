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

-- ============================================================================
-- HYBRID REAL-TIME QUERY FUNCTION
-- ============================================================================
-- This function provides near real-time OHLCV data by:
-- 1. Using continuous aggregates for historical data (fast, pre-computed)
-- 2. Using real-time aggregation on tick_data for recent data (live updates)
-- ============================================================================

CREATE OR REPLACE FUNCTION get_realtime_candles(
    p_instrument_token INTEGER,
    p_from_time TIMESTAMPTZ,
    p_to_time TIMESTAMPTZ,
    p_interval TEXT DEFAULT '1m'
)
RETURNS TABLE (
    bucket TIMESTAMPTZ,
    instrument_token INTEGER,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    open_interest BIGINT
) AS $$
DECLARE
    v_realtime_threshold TIMESTAMPTZ;
    v_bucket_interval INTERVAL;
BEGIN
    -- Define real-time threshold (last 2 hours = use tick_data)
    v_realtime_threshold := NOW() - INTERVAL '2 hours';
    
    -- Map interval string to PostgreSQL interval
    v_bucket_interval := CASE p_interval
        WHEN '1m' THEN INTERVAL '1 minute'
        WHEN '5m' THEN INTERVAL '5 minutes'
        WHEN '15m' THEN INTERVAL '15 minutes'
        WHEN '1h' THEN INTERVAL '1 hour'
        WHEN '1d' THEN INTERVAL '1 day'
        ELSE INTERVAL '1 minute'
    END;
    
    RETURN QUERY
    WITH historical_data AS (
        -- Historical data from continuous aggregates (fast)
        SELECT 
            c.bucket AS hist_bucket,
            c.instrument_token AS hist_token,
            c.open AS hist_open,
            c.high AS hist_high,
            c.low AS hist_low,
            c.close AS hist_close,
            c.volume AS hist_volume,
            c.open_interest AS hist_oi
        FROM (
            SELECT candles_1m.bucket, candles_1m.instrument_token, candles_1m.open, candles_1m.high, 
                   candles_1m.low, candles_1m.close, candles_1m.volume, candles_1m.open_interest
            FROM candles_1m WHERE p_interval = '1m'
            UNION ALL
            SELECT candles_5m.bucket, candles_5m.instrument_token, candles_5m.open, candles_5m.high, 
                   candles_5m.low, candles_5m.close, candles_5m.volume, candles_5m.open_interest
            FROM candles_5m WHERE p_interval = '5m'
            UNION ALL
            SELECT candles_15m.bucket, candles_15m.instrument_token, candles_15m.open, candles_15m.high, 
                   candles_15m.low, candles_15m.close, candles_15m.volume, candles_15m.open_interest
            FROM candles_15m WHERE p_interval = '15m'
            UNION ALL
            SELECT candles_1h.bucket, candles_1h.instrument_token, candles_1h.open, candles_1h.high, 
                   candles_1h.low, candles_1h.close, candles_1h.volume, candles_1h.open_interest
            FROM candles_1h WHERE p_interval = '1h'
            UNION ALL
            SELECT candles_1d.bucket, candles_1d.instrument_token, candles_1d.open, candles_1d.high, 
                   candles_1d.low, candles_1d.close, candles_1d.volume, candles_1d.open_interest
            FROM candles_1d WHERE p_interval = '1d'
        ) c
        WHERE c.instrument_token = p_instrument_token
          AND c.bucket >= p_from_time
          AND c.bucket < LEAST(p_to_time, v_realtime_threshold)
    ),
    realtime_data AS (
        -- Real-time data from tick_data (live, last 2 hours)
        SELECT 
            time_bucket(v_bucket_interval, tick_data.time) AS rt_bucket,
            tick_data.instrument_token AS rt_token,
            FIRST(tick_data.ltp, tick_data.time) AS rt_open,
            MAX(tick_data.ltp) AS rt_high,
            MIN(tick_data.ltp) AS rt_low,
            LAST(tick_data.ltp, tick_data.time) AS rt_close,
            MAX(tick_data.volume)::NUMERIC AS rt_volume,
            MAX(tick_data.open_interest) AS rt_oi
        FROM tick_data
        WHERE tick_data.instrument_token = p_instrument_token
          AND tick_data.time >= GREATEST(p_from_time, v_realtime_threshold)
          AND tick_data.time < p_to_time
        GROUP BY time_bucket(v_bucket_interval, tick_data.time), tick_data.instrument_token
    )
    -- Combine historical + real-time data
    SELECT hist_bucket, hist_token, hist_open, hist_high, hist_low, hist_close, hist_volume, hist_oi
    FROM historical_data
    UNION ALL
    SELECT rt_bucket, rt_token, rt_open, rt_high, rt_low, rt_close, rt_volume, rt_oi
    FROM realtime_data
    ORDER BY 1 ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_realtime_candles IS 
'Hybrid function that returns OHLCV candles with near real-time updates. 
Uses pre-computed continuous aggregates for historical data (>2h old) and 
real-time aggregation on tick_data for recent data (<2h old).';

