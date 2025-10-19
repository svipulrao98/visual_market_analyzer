"""Kite Connect automatic authentication."""
import hashlib
import pyotp
import requests
from typing import Dict
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from loguru import logger

from app.brokers.auth.base import BrokerAuthBase


class KiteAuth(BrokerAuthBase):
    """Automatic authentication for Kite Connect."""
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        username: str,
        password: str,
        totp_key: str,
        access_token: str = None
    ):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.username = username
        self.password = password
        self.totp_key = totp_key
        self.http_session = requests.Session()
        
        # If access token is provided, use it
        if access_token:
            self.access_token = access_token
            # Kite tokens are valid until next day 8:30 AM
            self.token_expires_at = self._calculate_token_expiry()
    
    def _calculate_token_expiry(self) -> datetime:
        """Calculate when the Kite token expires (next day 8:30 AM IST)."""
        now = datetime.now()
        next_expiry = (now + timedelta(days=1)).replace(
            hour=3, minute=0, second=0, microsecond=0  # 8:30 AM IST = 3:00 AM UTC
        )
        
        # If it's already past 8:30 AM today, expire today
        if now.hour >= 3:
            return now.replace(hour=3, minute=0, second=0, microsecond=0)
        
        return next_expiry
    
    async def authenticate(self) -> Dict:
        """
        Authenticate with Kite Connect using credentials and TOTP.
        
        Returns:
            Dict with access_token, user_id, and expires_at
        """
        try:
            logger.info("🔐 Starting Kite Connect authentication...")
            
            # Step 1: Get login URL
            login_url = f"https://kite.trade/connect/login?v=3&api_key={self.api_key}"
            initial_response = self.http_session.get(url=login_url)
            logger.info("✓ Retrieved login page")
            
            # Step 2: Login with credentials
            logger.info(f"🔑 Logging in as: {self.username}")
            login_response = self.http_session.post(
                url="https://kite.zerodha.com/api/login",
                data={"user_id": self.username, "password": self.password},
            )
            
            if login_response.status_code != 200:
                raise Exception(f"Login failed with status: {login_response.status_code}")
            
            login_data = login_response.json()
            if login_data.get("status") != "success":
                raise Exception(f"Login failed: {login_data.get('message', 'Unknown error')}")
            
            request_id = login_data["data"]["request_id"]
            logger.info("✓ Login successful")
            
            # Step 3: Complete 2FA with TOTP
            totp_token = pyotp.TOTP(self.totp_key).now()
            logger.info(f"🔐 Completing 2FA (TOTP: {totp_token})")
            
            twofa_response = self.http_session.post(
                url="https://kite.zerodha.com/api/twofa",
                data={
                    "user_id": self.username,
                    "request_id": request_id,
                    "twofa_value": totp_token,
                },
            )
            
            if twofa_response.status_code != 200:
                raise Exception(f"2FA failed with status: {twofa_response.status_code}")
            
            twofa_data = twofa_response.json()
            if twofa_data.get("status") != "success":
                raise Exception(f"2FA failed: {twofa_data.get('message', 'Unknown error')}")
            
            logger.info("✓ 2FA completed")
            
            # Step 4: Get request_token from redirect
            final_url = f"{login_url}&skip_session=true"
            final_response = self.http_session.get(url=final_url, allow_redirects=True)
            callback_url = final_response.url
            
            # Extract request_token
            parsed_url = urlparse(callback_url)
            query_params = parse_qs(parsed_url.query)
            
            if "request_token" not in query_params:
                raise Exception("request_token not found in callback URL")
            
            request_token = query_params["request_token"][0]
            logger.info(f"✓ Extracted request_token: {request_token[:20]}...")
            
            # Step 5: Exchange request_token for access_token
            checksum = hashlib.sha256(
                f"{self.api_key}{request_token}{self.api_secret}".encode()
            ).hexdigest()
            
            token_response = requests.post(
                url="https://api.kite.trade/session/token",
                data={
                    "api_key": self.api_key,
                    "request_token": request_token,
                    "checksum": checksum,
                },
            )
            token_response.raise_for_status()
            
            token_data = token_response.json()
            if token_data.get("status") != "success":
                raise Exception(f"Token exchange failed: {token_data}")
            
            access_token = token_data["data"]["access_token"]
            user_id = token_data["data"]["user_id"]
            
            logger.info(f"✅ Authentication successful!")
            logger.info(f"   User: {user_id}")
            logger.info(f"   Token: {access_token[:20]}...")
            
            return {
                "access_token": access_token,
                "user_id": user_id,
                "expires_at": self._calculate_token_expiry(),
            }
            
        except Exception as e:
            logger.error(f"❌ Kite authentication failed: {e}")
            raise

