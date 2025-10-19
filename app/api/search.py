"""Instrument search API for Grafana integration."""

from fastapi import APIRouter, Query
from typing import List, Dict
from loguru import logger

from app.database.connection import get_db_pool

router = APIRouter()


@router.get("/instruments")
async def search_instruments(
    q: str = Query("", description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
) -> List[Dict]:
    """
    Search instruments by symbol or name.

    Returns format compatible with Grafana variable queries.
    """
    try:
        pool = await get_db_pool()

        # If no query, return popular instruments
        if not q or len(q) < 2:
            query = """
                SELECT 
                    CONCAT(symbol, ' - ', segment, ' (', exchange, ')') as text,
                    token as value
                FROM instruments
                WHERE segment IN ('INDICES', 'NSE', 'NFO-FUT')
                    AND symbol IN (
                        'NIFTY 50', 'NIFTY BANK', 'SENSEX',
                        'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
                        'SBIN', 'KOTAKBANK', 'HDFC', 'BAJFINANCE'
                    )
                ORDER BY 
                    CASE segment 
                        WHEN 'INDICES' THEN 1
                        WHEN 'NSE' THEN 2
                        WHEN 'NFO-FUT' THEN 3
                        ELSE 4
                    END,
                    symbol
                LIMIT $1
            """
            params = (limit,)
        else:
            # Search by symbol (case-insensitive, supports partial match)
            search_pattern = f"%{q.upper()}%"
            query = """
                SELECT 
                    CONCAT(symbol, ' - ', segment, ' (', exchange, ')') as text,
                    token as value
                FROM instruments
                WHERE 
                    UPPER(symbol) LIKE $1
                    AND segment IN ('INDICES', 'NSE', 'BSE', 'NFO-FUT')
                ORDER BY 
                    -- Prioritize exact matches
                    CASE WHEN UPPER(symbol) = $2 THEN 1 ELSE 2 END,
                    -- Then by segment importance
                    CASE segment 
                        WHEN 'INDICES' THEN 1
                        WHEN 'NSE' THEN 2
                        WHEN 'NFO-FUT' THEN 3
                        WHEN 'BSE' THEN 4
                        ELSE 5
                    END,
                    -- Then alphabetically
                    symbol
                LIMIT $3
            """
            params = (search_pattern, q.upper(), limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = [{"text": row["text"], "value": str(row["value"])} for row in rows]

        logger.info(f"Instrument search: q='{q}' returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Error searching instruments: {e}")
        return [{"text": "Error loading instruments", "value": "256265"}]


@router.post("/search")
async def grafana_search_target(body: Dict = None) -> List[str]:
    """
    Grafana JSON datasource search endpoint.
    Returns list of available metrics/targets.
    """
    return ["instruments"]


@router.post("/query")
async def grafana_query(body: Dict = None) -> List[Dict]:
    """
    Grafana JSON datasource query endpoint.
    Not used for variables, but required for plugin compatibility.
    """
    return []


@router.get("/")
async def health():
    """Health check for search API."""
    return {"status": "ok", "service": "instrument-search"}
