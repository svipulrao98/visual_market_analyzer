"""Async backfill trigger endpoint for Grafana integration."""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from typing import Dict
from loguru import logger

from app.brokers import get_broker
from app.services.candle_service import CandleService
from app.services.auto_backfill import update_backfill_status

router = APIRouter()


@router.post("/trigger")
async def trigger_backfill(
    background_tasks: BackgroundTasks,
    instrument_token: int = Query(...),
    from_date: str = Query(...),
    to_date: str = Query(...),
    interval: str = Query("1m", regex="^(1m|5m|15m|1h|1d)$"),
) -> Dict:
    """
    Trigger async backfill for missing data.
    Returns immediately, backfill runs in background.

    Perfect for Grafana: call this, then query TimescaleDB directly.
    """
    try:
        # Parse dates
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

        # Validate
        if from_dt > to_dt:
            raise HTTPException(
                status_code=400, detail="from_date must be before to_date"
            )
        if from_dt > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400, detail="from_date cannot be in the future"
            )

        # Trigger background backfill
        background_tasks.add_task(
            _async_backfill,
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval=interval,
        )

        logger.info(
            f"🔄 Backfill triggered for token={instrument_token}, "
            f"range={from_dt.date()} to {to_dt.date()}, interval={interval}"
        )

        return {
            "success": True,
            "message": "Backfill triggered",
            "instrument_token": instrument_token,
            "from_date": from_dt.isoformat(),
            "to_date": to_dt.isoformat(),
            "interval": interval,
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering backfill: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger backfill: {str(e)}"
        )


@router.get("/trigger")
async def trigger_backfill_get(
    background_tasks: BackgroundTasks,
    instrument_token: int = Query(...),
    from_date: str = Query(...),
    to_date: str = Query(...),
    interval: str = Query("1m", regex="^(1m|5m|15m|1h|1d)$"),
) -> Dict:
    """
    GET version of trigger endpoint (for Grafana Infinity plugin).
    Infinity plugin works better with GET requests for initial calls.
    """
    return await trigger_backfill(
        background_tasks=background_tasks,
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )


async def _async_backfill(
    instrument_token: int,
    from_date: datetime,
    to_date: datetime,
    interval: str,
):
    """
    Background task to perform the actual backfill.
    This runs async and doesn't block the API response.
    """
    try:
        logger.info(
            f"🚀 Starting background backfill: token={instrument_token}, "
            f"interval={interval}, range={from_date.date()} to {to_date.date()}"
        )

        broker = get_broker()
        service = CandleService(broker)

        # This will detect gaps and fill them
        candles = await service.get_candles(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
        )

        # Update tracking
        await update_backfill_status(instrument_token, from_date, to_date, len(candles))

        logger.info(
            f"✅ Background backfill complete: {len(candles)} candles available "
            f"for token={instrument_token}, interval={interval}"
        )

    except Exception as e:
        logger.error(f"❌ Background backfill failed: {e}")
        import traceback

        logger.error(traceback.format_exc())


@router.get("/status")
async def backfill_status() -> Dict:
    """
    Check backfill service status.
    """
    return {
        "status": "ready",
        "service": "async-backfill",
        "description": "Trigger with /api/backfill/trigger?instrument_token=X&from_date=Y&to_date=Z&interval=1m",
    }
