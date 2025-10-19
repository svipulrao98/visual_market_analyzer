#!/usr/bin/env python
"""Test Kite authentication system."""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.brokers.auth.kite_auth import KiteAuth
from loguru import logger


async def test_auth():
    """Test Kite authentication."""
    logger.info("=" * 60)
    logger.info("Testing Kite Authentication System")
    logger.info("=" * 60)

    # Check configuration
    logger.info("\n📋 Checking configuration...")
    required_vars = {
        "KITE_API_KEY": settings.kite_api_key,
        "KITE_API_SECRET": settings.kite_api_secret,
        "KITE_USERNAME": settings.kite_username,
        "KITE_PASSWORD": settings.kite_password,
        "KITE_TOTP_KEY": settings.kite_totp_key,
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
        return False

    logger.info("✓ All required variables present")

    # Test authentication
    logger.info("\n🔐 Testing authentication...")
    try:
        auth = KiteAuth(
            api_key=settings.kite_api_key,
            api_secret=settings.kite_api_secret,
            username=settings.kite_username,
            password=settings.kite_password,
            totp_key=settings.kite_totp_key,
            access_token=settings.kite_access_token,
        )

        # Get valid token (will authenticate if needed)
        token = await auth.get_valid_token()

        logger.info("\n✅ Authentication Test PASSED")
        logger.info(f"   Access Token: {token[:30]}...")
        logger.info(f"   User ID: {auth.user_id}")
        logger.info(f"   Expires At: {auth.token_expires_at}")

        # Test token validation
        logger.info("\n🔍 Testing token validation...")
        is_valid = auth.is_token_valid()
        logger.info(f"   Token valid: {is_valid}")

        if is_valid:
            logger.info("✓ Token validation working correctly")

        return True

    except Exception as e:
        logger.error(f"\n❌ Authentication Test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    success = await test_auth()

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("🎉 All tests PASSED!")
        logger.info("=" * 60)
        return 0
    else:
        logger.info("❌ Tests FAILED")
        logger.info("=" * 60)
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
