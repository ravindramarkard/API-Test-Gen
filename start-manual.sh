#!/bin/bash

# Manual start script (without Docker)

echo "🚀 Starting API Test Generation Platform (Manual Mode)..."

# Check prerequisites
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL client not found. Make sure PostgreSQL is installed and running."
fi

# Backend setup
echo "📦 Setting up backend..."
cd backend

if ! command -v poetry &> /dev/null; then
    echo "📥 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "📥 Installing backend dependencies..."
poetry install

echo "🔧 Setting up environment..."
if [ ! -f .env ]; then
    cat > .env << EOF
DATABASE_URL=postgresql://apitest:apitest123@localhost:5432/apitest_db
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
ENCRYPTION_KEY=
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379/0
EOF
    echo "✅ Created .env file"
fi

echo "🗄️  Running database migrations..."
poetry run alembic upgrade head || echo "⚠️  Make sure PostgreSQL is running and database exists"

echo "🚀 Starting backend server..."
poetry run uvicorn app.main:app --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

cd ..

# Frontend setup
echo ""
echo "📦 Setting up frontend..."
cd frontend

if [ ! -d node_modules ]; then
    echo "📥 Installing frontend dependencies..."
    npm install
fi

if [ ! -f .env ]; then
    echo "REACT_APP_API_URL=http://localhost:8000/api/v1" > .env
    echo "✅ Created .env file"
fi

echo "🚀 Starting frontend server..."
npm start &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

cd ..

echo ""
echo "✅ Services started!"
echo ""
echo "📍 Access points:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "🛑 To stop: kill $BACKEND_PID $FRONTEND_PID"
echo ""




