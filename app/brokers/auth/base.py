"""Base class for broker authentication."""
from abc import ABC, abstractmethod
from typing import Optional, Dict
from datetime import datetime, timedelta
from loguru import logger


class BrokerAuthBase(ABC):
    """Base class for broker authentication."""
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.user_id: Optional[str] = None
        
    @abstractmethod
    async def authenticate(self) -> Dict:
        """
        Authenticate with the broker and obtain access token.
        
        Returns:
            Dict containing:
                - access_token: str
                - user_id: str
                - expires_at: datetime
        """
        pass
    
    def is_token_valid(self) -> bool:
        """Check if current token is valid."""
        if not self.access_token:
            return False
        
        if not self.token_expires_at:
            return True  # No expiry set, assume valid
        
        # Add 5 minute buffer before expiry
        return datetime.now() < (self.token_expires_at - timedelta(minutes=5))
    
    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self.is_token_valid():
            logger.info(f"Using existing valid token (expires: {self.token_expires_at})")
            return self.access_token
        
        logger.info("Token expired or invalid, authenticating...")
        result = await self.authenticate()
        
        self.access_token = result['access_token']
        self.user_id = result.get('user_id')
        self.token_expires_at = result.get('expires_at')
        
        logger.info(f"✓ Authentication successful for user: {self.user_id}")
        logger.info(f"✓ Token expires at: {self.token_expires_at}")
        
        return self.access_token

