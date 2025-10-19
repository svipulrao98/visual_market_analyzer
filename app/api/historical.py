"""Historical data API endpoints.

NOTE: The /candles endpoint has been moved to app/api/candles.py with smart gap filling.
This file now only contains the raw tick data endpoint.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.historical import HistoricalDataService


router = APIRouter()


@router.get("/ticks")
async def get_tick_data(
    instrument_token: int = Query(...),
    from_date: str = Query(...),
    to_date: str = Query(...),
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
            instrument_token, from_dt, to_dt
        )

        return {
            "success": True,
            "instrument_token": instrument_token,
            "count": len(ticks),
            "ticks": ticks,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Failed to get tick data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tick data")
