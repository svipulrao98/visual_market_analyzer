"""FastAPI main application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import instruments, historical, websocket, candles, search, backfill
from app.database.connection import init_db, close_db
from app.utils.logger import setup_logger
from app.services.data_ingestion import data_ingestion_service
from app.services.auto_backfill import start_auto_backfill
from app.services.realtime_streaming import realtime_service
from app.services.instruments import InstrumentService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logger()
    await init_db()

    # Sync instruments from broker (on first startup or if empty)
    import asyncio
    from loguru import logger

    try:
        logger.info("📥 syncing instruments from broker...")
        synced = await InstrumentService.sync_instruments_from_broker()
        logger.info(f"✅ Synced {synced} instruments")
    except Exception as e:
        logger.error(f"Failed to sync instruments: {e}")

    # Start background tasks
    flush_task = asyncio.create_task(data_ingestion_service.start_flush_loop())
    await start_auto_backfill()

    # Start real-time streaming (after backfill service initializes)
    await asyncio.sleep(10)  # Give backfill time to populate backfill_status
    await realtime_service.start_auto_streaming()

    yield

    # Shutdown
    flush_task.cancel()
    await data_ingestion_service.flush_buffer()
    await realtime_service.stop_streaming()
    await close_db()


app = FastAPI(
    title="Trading Helper API",
    description="Real-time trading data ingestion and visualization system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Grafana and other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(instruments.router, prefix="/api/instruments", tags=["instruments"])
app.include_router(candles.router, prefix="/api/candles", tags=["candles"])
app.include_router(historical.router, prefix="/api/historical", tags=["historical"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(backfill.router, prefix="/api/backfill", tags=["backfill"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Trading Helper API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
