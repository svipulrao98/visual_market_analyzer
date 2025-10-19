# Kite Auto-Authentication Setup Guide

## Overview

The system now supports **automatic authentication** for Kite Connect. You no longer need to manually update the access token daily!

## What Changed

### ✅ New Features

1. **Automatic Token Generation**: System automatically obtains access tokens using your credentials
2. **Token Expiry Management**: Automatically refreshes tokens when expired
3. **Broker Agnostic Design**: Easy to extend for other brokers (Fyers coming soon)
4. **Seamless Integration**: Works transparently with existing broker code

### 📁 New Files

```
app/brokers/auth/
├── __init__.py              # Auth module exports
├── base.py                  # Base authentication class
├── kite_auth.py            # Kite-specific authentication
└── README.md               # Detailed documentation
```

### 🔧 Modified Files

- `app/config.py` - Added auth configuration variables
- `app/brokers/kite.py` - Integrated automatic authentication
- `requirements.txt` - Added `pyotp` dependency
- `env.example` - Updated with auth variables

## Setup Instructions

### 1. Update Your `.env` File

Add these variables to your `.env` file:

```bash
# Kite API Credentials
KITE_API_KEY=ktzcudyx40jtix30
KITE_API_SECRET=1cfee9p7wazf2215lrpshjhks04z3y1c
KITE_USERNAME=HR5807
KITE_PASSWORD=Vipsy@98
KITE_TOTP_KEY=GOYURVMSKIVA2RMYVUDZKH72K6RIB74X
KITE_ACCESS_TOKEN=
```

**Note**: Leave `KITE_ACCESS_TOKEN` empty to enable auto-authentication!

### 2. Rebuild and Restart Services

```bash
# Rebuild FastAPI container with new dependencies
docker-compose build fastapi

# Restart services
docker-compose up -d

# Check logs
docker-compose logs -f fastapi
```

### 3. Test Authentication

```bash
# Run the test script
docker-compose exec fastapi python scripts/test_kite_auth.py
```

Expected output:
```
✅ Authentication Test PASSED
   Access Token: abcd1234...
   User ID: HR5807
   Expires At: 2025-10-19 03:00:00
```

## How It Works

### Authentication Flow

1. **Check Existing Token**: System first checks if existing token is valid
2. **Auto-Login**: If expired, automatically logs in with credentials
3. **2FA/TOTP**: Completes two-factor authentication using TOTP key
4. **Token Exchange**: Extracts request_token and exchanges for access_token
5. **Token Storage**: Stores token in memory with expiry tracking
6. **Auto-Refresh**: Refreshes automatically when needed (5-minute buffer)

### Token Validity

- Kite tokens are valid until **8:30 AM IST** next day
- System automatically refreshes before expiry
- No manual intervention required!

## Usage

### In Your Code

Authentication happens automatically - no code changes needed:

```python
from app.brokers.kite import KiteBroker

# Auto-authentication happens on initialization
broker = KiteBroker()

# All API calls automatically ensure valid token
instruments = await broker.get_instruments()
historical = await broker.fetch_historical(...)
```

### Manual Token (Alternative)

If you prefer manual token management:

1. Set `KITE_ACCESS_TOKEN` in `.env`
2. Leave auth variables empty
3. Update token daily before 8:30 AM IST

## Configuration Options

### Auto-Authentication (Recommended)

```bash
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_USERNAME=your_user_id
KITE_PASSWORD=your_password
KITE_TOTP_KEY=your_totp_secret
KITE_ACCESS_TOKEN=  # Leave empty
```

### Manual Token

```bash
KITE_API_KEY=your_api_key
KITE_ACCESS_TOKEN=your_daily_token
# Auth variables not needed
```

## Troubleshooting

### Authentication Failed

**Check:**
- All credentials are correct in `.env`
- TOTP secret is valid (test with Google Authenticator)
- No typos in credentials
- Account is not locked

**Solutions:**
- Verify credentials on Kite web login
- Check TOTP code matches authenticator app
- Ensure no active Kite sessions
- Review logs: `docker-compose logs -f fastapi`

### Import Errors

If you see `ModuleNotFoundError: No module named 'pyotp'`:

```bash
docker-compose build fastapi
docker-compose up -d
```

### Token Expired Too Soon

- Check system timezone is correct
- Verify server time matches IST
- Review logs for expiry calculation

## Security Best Practices

✅ **DO:**
- Store credentials in `.env` only
- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate credentials periodically

❌ **DON'T:**
- Commit `.env` to version control
- Share credentials in code or logs
- Use same credentials across environments
- Hardcode credentials

## Future Enhancements

Coming soon:
- ✅ Fyers auto-authentication
- ✅ Token persistence across restarts
- ✅ Multi-user support
- ✅ Session management dashboard

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f fastapi`
2. Review `app/brokers/auth/README.md`
3. Test with: `docker-compose exec fastapi python scripts/test_kite_auth.py`

## API Documentation

See `/docs` endpoint when server is running: http://localhost:8000/docs

---

**Enjoy hassle-free trading! 🚀**

