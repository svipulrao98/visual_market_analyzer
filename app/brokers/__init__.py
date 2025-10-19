"""Broker interface implementations."""
from app.brokers.base import BrokerInterface
from app.brokers.kite import KiteBroker
from app.brokers.fyers import FyersBroker
from app.config import settings


def get_broker() -> BrokerInterface:
    """Get broker instance based on configuration."""
    if settings.broker.lower() == "kite":
        return KiteBroker()
    elif settings.broker.lower() == "fyers":
        return FyersBroker()
    else:
        raise ValueError(f"Unknown broker: {settings.broker}")

