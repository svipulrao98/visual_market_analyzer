"""Smart candles API endpoint with automatic gap filling."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict
from loguru import logger

from app.services.candle_service import CandleService
from app.brokers import get_broker
from app.services.auto_backfill import track_instrument

router = APIRouter()


class CandleRequest(BaseModel):
    """Request model for candle data."""

    instrument_token: int
    from_date: datetime
    to_date: datetime
    interval: str = "1m"  # 1m, 5m, 15m, 1h, 1d


@router.get("/")
async def get_candles(
    instrument_token: int = Query(..., description="Instrument token"),
    from_date: str = Query(
        ..., description="Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"
    ),
    to_date: str = Query(
        ..., description="End date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)"
    ),
    interval: str = Query(
        "1m", regex="^(1m|5m|15m|1h|1d)$", description="Candle interval"
    ),
):
    """
    Get candle data with automatic gap filling.

    This endpoint:
    1. Queries TimescaleDB continuous aggregates first
    2. Detects missing data automatically
    3. Backfills from broker API if gaps exist
    4. Returns complete dataset

    No need for separate backfill endpoint!

    Args:
        instrument_token: Instrument token
        from_date: Start date/datetime
        to_date: End date/datetime
        interval: Candle interval (1m, 5m, 15m, 1h, 1d)

    Returns:
        List of candles with OHLCV data
    """
    try:
        # Parse dates (support both formats) and make them timezone-aware
        from datetime import timezone

        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )

        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Validate dates
        if from_dt > to_dt:
            raise HTTPException(
                status_code=400, detail="from_date must be before to_date"
            )

        if from_dt > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400, detail="from_date cannot be in the future"
            )

        # Track instrument for auto-backfill
        track_instrument(instrument_token)

        # Get broker instance
        broker = get_broker()

        # Create candle service
        service = CandleService(broker)

        # Get candles with automatic gap filling
        candles = await service.get_candles(instrument_token, from_dt, to_dt, interval)

        return {
            "success": True,
            "instrument_token": instrument_token,
            "interval": interval,
            "from_date": from_dt.isoformat(),
            "to_date": to_dt.isoformat(),
            "count": len(candles),
            "candles": candles,
        }

    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        import traceback

        logger.error(f"Error fetching candles: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch candles: {str(e)}"
        )


@router.post("/")
async def post_candles(request: CandleRequest):
    """
    Get candle data with automatic gap filling (POST method).

    Alternative POST endpoint for the same functionality.
    Useful for complex queries or when URL length is a concern.
    """
    try:
        # Get broker instance
        broker = get_broker()

        # Create candle service
        service = CandleService(broker)

        # Get candles with automatic gap filling
        candles = await service.get_candles(
            request.instrument_token,
            request.from_date,
            request.to_date,
            request.interval,
        )

        return {
            "success": True,
            "instrument_token": request.instrument_token,
            "interval": request.interval,
            "from_date": request.from_date.isoformat(),
            "to_date": request.to_date.isoformat(),
            "count": len(candles),
            "candles": candles,
        }

    except Exception as e:
        logger.error(f"Error fetching candles: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch candles: {str(e)}"
        )
