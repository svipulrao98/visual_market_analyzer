# Broker Authentication System

This module provides automatic authentication for broker APIs. The system is designed to be broker-agnostic, allowing easy extension for multiple brokers.

## Architecture

```
BrokerAuthBase (Abstract)
    ├── KiteAuth (Kite Connect)
    └── FyersAuth (Future implementation)
```

## Features

- **Automatic Token Generation**: Automatically obtains access tokens using credentials
- **Token Expiry Management**: Tracks token expiry and refreshes automatically
- **Broker Agnostic**: Easy to extend for multiple brokers
- **Secure**: Credentials stored in environment variables only

## Kite Connect Authentication

### Setup

Add these variables to your `.env` file:

```bash
# Required
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_USERNAME=your_user_id
KITE_PASSWORD=your_password
KITE_TOTP_KEY=your_totp_secret

# Optional (leave empty for auto-authentication)
KITE_ACCESS_TOKEN=
```

### How It Works

1. **Login**: Authenticates with Zerodha using username/password
2. **2FA**: Completes TOTP-based two-factor authentication
3. **Token Exchange**: Extracts request_token and exchanges it for access_token
4. **Auto-Refresh**: Automatically refreshes token when expired

### Token Validity

Kite Connect tokens are valid until **8:30 AM IST next day**. The system automatically:
- Checks token validity before API calls
- Refreshes token if expired or about to expire (5-minute buffer)
- Logs authentication status

### Usage

The authentication is handled automatically by the `KiteBroker` class:

```python
from app.brokers.kite import KiteBroker

# Auto-authentication happens automatically
broker = KiteBroker()

# All API calls will ensure valid token
instruments = await broker.get_instruments()
```

### Manual Token (Alternative)

If you prefer to manage tokens manually:

1. Get your access token from Kite Connect dashboard
2. Set `KITE_ACCESS_TOKEN` in `.env`
3. Leave authentication variables empty
4. Token must be updated daily before 8:30 AM IST

## Adding New Brokers

To add a new broker authentication:

1. Create a new class inheriting from `BrokerAuthBase`
2. Implement the `authenticate()` method
3. Update the broker implementation to use the auth class

Example:

```python
from app.brokers.auth.base import BrokerAuthBase

class FyersAuth(BrokerAuthBase):
    def __init__(self, app_id, secret, username, password):
        super().__init__()
        self.app_id = app_id
        # ... store credentials
    
    async def authenticate(self) -> Dict:
        # Implement Fyers-specific authentication
        # Return dict with access_token, user_id, expires_at
        pass
```

## Security Notes

- Never commit `.env` file with actual credentials
- Use environment variables in production
- TOTP secret should be kept secure
- Credentials are only used during authentication, not stored in memory

## Troubleshooting

### Authentication Failed

Check:
- Credentials are correct in `.env`
- TOTP secret is valid (test with authenticator app)
- Account is active and not locked
- No active session exists (logout from Kite web/app first)

### Token Expired Too Soon

The system calculates expiry based on Kite's policy (8:30 AM IST). If issues persist:
- Check system timezone
- Verify server time is correct
- Manual tokens require daily update

### Import Errors

If you see import errors for `kiteconnect` or `pyotp`:

```bash
pip install kiteconnect pyotp
```

Or rebuild Docker:

```bash
docker-compose build fastapi
docker-compose up -d
```

