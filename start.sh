#!/bin/bash

# Start script for API Test Generation Platform

echo "🚀 Starting API Test Generation Platform..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    echo ""
    echo "Alternatively, you can run the project manually:"
    echo "  Backend: cd backend && poetry install && poetry run uvicorn app.main:app --reload"
    echo "  Frontend: cd frontend && npm install && npm start"
    exit 1
fi

# Check if services are already running
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Some services are already running. Stopping them first..."
    docker-compose down
fi

echo "📦 Building Docker images..."
docker-compose build

echo "🔧 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

echo "🗄️  Initializing database..."
docker-compose exec -T backend poetry run alembic upgrade head || echo "⚠️  Database migration may have failed. Check logs with: docker-compose logs backend"

echo ""
echo "✅ Services started!"
echo ""
echo "📍 Access points:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo "   Health:    http://localhost:8000/health"
echo ""
echo "📊 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"
echo ""


