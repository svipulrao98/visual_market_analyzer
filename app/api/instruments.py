"""Instrument management API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.services.instruments import InstrumentService
from app.database.connection import get_db_pool
from app.database.models import SubscriptionQueries


router = APIRouter()


class InstrumentResponse(BaseModel):
    """Instrument response model."""
    id: int
    token: int
    symbol: str
    exchange: str
    segment: str
    instrument_type: Optional[str] = None
    lot_size: Optional[int] = None


class SubscribeRequest(BaseModel):
    """Request model for subscribing to instruments."""
    tokens: List[int]


class SubscribeResponse(BaseModel):
    """Response model for subscription."""
    success: bool
    message: str
    subscribed_tokens: List[int]


@router.get("/", response_model=List[InstrumentResponse])
async def get_instruments(
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """
    Get all instruments with pagination.
    
    Args:
        limit: Maximum number of instruments to return
        offset: Number of instruments to skip
    """
    try:
        instruments = await InstrumentService.get_all_instruments(limit, offset)
        return instruments
    except Exception as e:
        logger.error(f"Failed to get instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch instruments")


@router.get("/search")
async def search_instruments(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Search instruments by symbol or exchange.
    
    Args:
        q: Search query
        limit: Maximum number of results
    """
    try:
        instruments = await InstrumentService.search_instruments(q, limit)
        return instruments
    except Exception as e:
        logger.error(f"Failed to search instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to search instruments")


@router.get("/{token}")
async def get_instrument(token: int):
    """
    Get instrument details by token.
    
    Args:
        token: Instrument token
    """
    try:
        instrument = await InstrumentService.get_instrument_by_token(token)
        if not instrument:
            raise HTTPException(status_code=404, detail="Instrument not found")
        return instrument
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instrument: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch instrument")


@router.post("/sync")
async def sync_instruments():
    """
    Sync instruments from broker to database.
    
    This endpoint fetches the latest instrument master from the broker
    and updates the database.
    """
    try:
        count = await InstrumentService.sync_instruments_from_broker()
        return {
            "success": True,
            "message": f"Synced {count} instruments",
            "count": count
        }
    except Exception as e:
        logger.error(f"Failed to sync instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync instruments")


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe_instruments(request: SubscribeRequest):
    """
    Subscribe to instruments for real-time data streaming.
    
    Args:
        request: List of instrument tokens to subscribe
    """
    try:
        pool = await get_db_pool()
        
        for token in request.tokens:
            await SubscriptionQueries.subscribe_instrument(pool, token)
        
        logger.info(f"Subscribed to {len(request.tokens)} instruments")
        
        return SubscribeResponse(
            success=True,
            message=f"Subscribed to {len(request.tokens)} instruments",
            subscribed_tokens=request.tokens
        )
    except Exception as e:
        logger.error(f"Failed to subscribe instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to subscribe instruments")


@router.post("/unsubscribe")
async def unsubscribe_instruments(request: SubscribeRequest):
    """
    Unsubscribe from instruments.
    
    Args:
        request: List of instrument tokens to unsubscribe
    """
    try:
        pool = await get_db_pool()
        
        for token in request.tokens:
            await SubscriptionQueries.unsubscribe_instrument(pool, token)
        
        logger.info(f"Unsubscribed from {len(request.tokens)} instruments")
        
        return {
            "success": True,
            "message": f"Unsubscribed from {len(request.tokens)} instruments",
            "tokens": request.tokens
        }
    except Exception as e:
        logger.error(f"Failed to unsubscribe instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to unsubscribe instruments")


@router.get("/subscriptions/list")
async def list_subscribed_instruments():
    """Get list of currently subscribed instruments."""
    try:
        pool = await get_db_pool()
        tokens = await SubscriptionQueries.get_subscribed_instruments(pool)
        
        return {
            "success": True,
            "count": len(tokens),
            "tokens": tokens
        }
    except Exception as e:
        logger.error(f"Failed to get subscribed instruments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subscriptions")

