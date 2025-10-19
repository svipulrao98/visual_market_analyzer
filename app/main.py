"""FastAPI main application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import instruments, historical, websocket
from app.database.connection import init_db, close_db
from app.utils.logger import setup_logger
from app.services.data_ingestion import data_ingestion_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logger()
    await init_db()
    
    # Start background tasks
    import asyncio
    flush_task = asyncio.create_task(data_ingestion_service.start_flush_loop())
    
    yield
    
    # Shutdown
    flush_task.cancel()
    await data_ingestion_service.flush_buffer()
    await close_db()


app = FastAPI(
    title="Trading Helper API",
    description="Real-time trading data ingestion and visualization system",
    version="1.0.0",
    lifespan=lifespan
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
app.include_router(historical.router, prefix="/api/historical", tags=["historical"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Trading Helper API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

