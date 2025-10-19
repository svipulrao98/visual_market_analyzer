#!/bin/bash

# Trading Helper System Setup Script

set -e

echo "======================================"
echo "Trading Helper System - Setup"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your broker API credentials!"
    echo "   nano .env  (or use your preferred editor)"
    echo ""
    read -p "Press Enter after you've updated .env with your credentials..."
else
    echo "✓ .env file already exists"
fi

echo ""
echo "Starting Docker services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "Initializing database..."
docker-compose exec -T fastapi python scripts/init_db.py

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Services are running:"
echo "  - FastAPI: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - TimescaleDB: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "Next steps:"
echo "  1. Sync instruments: docker-compose exec fastapi python scripts/seed_instruments.py"
echo "  2. Subscribe to instruments: docker-compose exec fastapi python scripts/subscribe_instruments.py 256265"
echo "  3. Start WebSocket streaming: curl -X POST http://localhost:8000/api/ws/start"
echo "  4. Access Grafana dashboard: http://localhost:3000"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop services: docker-compose down"
echo ""

