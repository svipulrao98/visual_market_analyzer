"""Historical data API endpoints."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.services.historical import HistoricalDataService


router = APIRouter()


class BackfillRequest(BaseModel):
    """Request model for historical data backfill."""
    instrument_token: int
    from_date: str  # Format: YYYY-MM-DD
    to_date: str    # Format: YYYY-MM-DD
    interval: str = "1m"  # 1m, 5m, 15m, 1h, 1d


class BackfillResponse(BaseModel):
    """Response model for backfill."""
    success: bool
    message: str
    candles_count: int


@router.post("/backfill", response_model=BackfillResponse)
async def backfill_historical_data(request: BackfillRequest):
    """
    Backfill historical data from broker.
    
    Args:
        request: Backfill parameters (instrument, date range, interval)
    """
    try:
        # Parse dates
        from_date = datetime.strptime(request.from_date, "%Y-%m-%d")
        to_date = datetime.strptime(request.to_date, "%Y-%m-%d")
        
        # Validate dates
        if from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date must be before to_date")
        
        if from_date > datetime.now():
            raise HTTPException(status_code=400, detail="from_date cannot be in the future")
        
        # Backfill data
        count = await HistoricalDataService.backfill_historical_data(
            request.instrument_token,
            from_date,
            to_date,
            request.interval
        )
        
        return BackfillResponse(
            success=True,
            message=f"Backfilled {count} candles",
            candles_count=count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to backfill historical data: {e}")
        raise HTTPException(status_code=500, detail="Failed to backfill data")


@router.get("/candles")
async def get_candles(
    instrument_token: int = Query(...),
    interval: str = Query("1m", regex="^(1m|5m|15m|1h|1d)$"),
    from_date: str = Query(...),
    to_date: str = Query(...)
):
    """
    Get historical candle data.
    
    Args:
        instrument_token: Instrument token
        interval: Candle interval (1m, 5m, 15m, 1h, 1d)
        from_date: Start date (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)
    """
    try:
        # Parse dates (support both date and datetime formats)
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Get candles
        candles = await HistoricalDataService.get_candles(
            instrument_token,
            interval,
            from_dt,
            to_dt
        )
        
        return {
            "success": True,
            "instrument_token": instrument_token,
            "interval": interval,
            "count": len(candles),
            "candles": candles
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Failed to get candles: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch candles")


@router.get("/ticks")
async def get_tick_data(
    instrument_token: int = Query(...),
    from_date: str = Query(...),
    to_date: str = Query(...)
):
    """
    Get raw tick data.
    
    Args:
        instrument_token: Instrument token
        from_date: Start date (YYYY-MM-DD HH:MM:SS)
        to_date: End date (YYYY-MM-DD HH:MM:SS)
    """
    try:
        # Parse dates
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Get ticks
        ticks = await HistoricalDataService.get_tick_data(
            instrument_token,
            from_dt,
            to_dt
        )
        
        return {
            "success": True,
            "instrument_token": instrument_token,
            "count": len(ticks),
            "ticks": ticks
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Failed to get tick data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tick data")

