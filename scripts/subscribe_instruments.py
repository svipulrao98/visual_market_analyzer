"""Subscribe to specific instruments for real-time streaming."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import init_db, close_db, get_db_pool
from app.database.models import SubscriptionQueries
from loguru import logger


async def subscribe_instruments(tokens: list[int]):
    """
    Subscribe to instruments.
    
    Args:
        tokens: List of instrument tokens to subscribe
    """
    try:
        logger.info("Connecting to database...")
        await init_db()
        
        pool = await get_db_pool()
        
        for token in tokens:
            await SubscriptionQueries.subscribe_instrument(pool, token)
            logger.info(f"Subscribed to instrument: {token}")
        
        logger.info(f"Successfully subscribed to {len(tokens)} instruments!")
        
    except Exception as e:
        logger.error(f"Failed to subscribe instruments: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    # Example: Subscribe to NIFTY 50 and BANKNIFTY futures
    # Replace these tokens with actual instrument tokens from your broker
    
    # Kite example tokens (these are examples, replace with actual tokens):
    # NIFTY 50 Index: 256265
    # BANKNIFTY Index: 260105
    
    example_tokens = [
        256265,  # NIFTY 50
        260105,  # BANKNIFTY
    ]
    
    if len(sys.argv) > 1:
        # Accept tokens as command line arguments
        tokens = [int(token) for token in sys.argv[1:]]
    else:
        tokens = example_tokens
        logger.info("Using example tokens. Pass tokens as arguments: python subscribe_instruments.py 256265 260105")
    
    asyncio.run(subscribe_instruments(tokens))

