# Python Version Configuration

## Version: Python 3.11

This project is **strictly configured to use Python 3.11** for consistency, performance, and compatibility.

## Why Python 3.11?

- **Performance**: Up to 25% faster than Python 3.10
- **Better Error Messages**: Enhanced traceback information
- **Modern Features**: Support for newer async/await patterns
- **Type Hints**: Improved type hinting support
- **Stability**: Mature and stable release

## Configuration Files

### Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.11-slim
```
The Docker image explicitly uses Python 3.11 slim variant.

### Version Files
- `.python-version` → Contains `3.11` (for pyenv and other version managers)
- `runtime.txt` → Contains `python-3.11` (for cloud platforms)

### Documentation
All documentation files specify Python 3.11:
- `README.md` → "Python 3.11"
- `QUICKSTART.md` → "Python 3.11"
- `PROJECT_SUMMARY.md` → "Python 3.11"
- `claude.md` → "Python 3.11"

## Local Development Setup

### Check Your Python Version
```bash
python --version
# Should output: Python 3.11.x
```

### Install Python 3.11

**macOS (using Homebrew):**
```bash
brew install python@3.11
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and select version 3.11.x

**Using pyenv (Recommended):**
```bash
pyenv install 3.11
pyenv local 3.11
```

### Create Virtual Environment
```bash
# Create venv with Python 3.11
python3.11 -m venv venv

# Activate
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Verify version
python --version
# Should show: Python 3.11.x

# Install dependencies
pip install -r requirements.txt
```

## Docker Usage (Recommended)

The easiest way to ensure Python 3.11 consistency is to use Docker:

```bash
# All containers will use Python 3.11
docker-compose up -d

# Verify Python version in container
docker-compose exec fastapi python --version
```

## Dependency Compatibility

All packages in `requirements.txt` are compatible with Python 3.11:

- ✅ FastAPI 0.104+
- ✅ asyncpg 0.29+
- ✅ redis 5.0+
- ✅ All other dependencies

## CI/CD Considerations

When setting up CI/CD pipelines, ensure Python 3.11 is used:

**GitHub Actions:**
```yaml
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
```

**GitLab CI:**
```yaml
image: python:3.11-slim
```

**CircleCI:**
```yaml
docker:
  - image: python:3.11-slim
```

## Troubleshooting

### Wrong Python Version

**Problem:** `python --version` shows different version

**Solution:**
```bash
# Use explicit python3.11 command
python3.11 --version

# Or create alias
alias python=python3.11

# Or use pyenv
pyenv global 3.11
```

### Package Compatibility Issues

**Problem:** Package won't install with Python 3.11

**Solution:**
```bash
# Update pip
pip install --upgrade pip

# Try specific package version
pip install package_name==version
```

### Docker Python Version Mismatch

**Problem:** Container using wrong Python version

**Solution:**
```bash
# Rebuild containers
docker-compose build --no-cache fastapi

# Verify
docker-compose exec fastapi python --version
```

## Verification Checklist

Before deploying or running locally, verify:

- [ ] `python --version` shows 3.11.x
- [ ] `docker-compose exec fastapi python --version` shows 3.11.x
- [ ] All packages install without errors
- [ ] FastAPI starts successfully
- [ ] No deprecation warnings related to Python version

## Future Upgrades

When Python 3.12+ becomes stable and all dependencies are compatible:

1. Update `Dockerfile`: `FROM python:3.12-slim`
2. Update `.python-version`: `3.12`
3. Update `runtime.txt`: `python-3.12`
4. Update all documentation
5. Test all dependencies
6. Update this file

## Support

For Python 3.11 specific issues:
- [Python 3.11 Documentation](https://docs.python.org/3.11/)
- [Python 3.11 Release Notes](https://docs.python.org/3.11/whatsnew/3.11.html)
- [Python 3.11 Migration Guide](https://docs.python.org/3.11/whatsnew/3.11.html#porting-to-python-3-11)

