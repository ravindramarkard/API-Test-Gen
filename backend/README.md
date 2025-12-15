# API Test Generation Backend

FastAPI backend for automated API test generation from OpenAPI/Swagger specifications.

## Setup

### Using Poetry (Recommended)

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run database migrations
poetry run alembic upgrade head

# Start the server
poetry run uvicorn app.main:app --reload
```

### Using Docker

```bash
docker-compose up backend
```

## Environment Variables

Create a `.env` file in the backend directory:

```env
DATABASE_URL=postgresql://apitest:apitest123@localhost:5432/apitest_db
SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=your-encryption-key-change-in-production
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379/0
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

## Testing

```bash
poetry run pytest
```

## Project Structure

```
backend/
├── app/
│   ├── api/           # API endpoints
│   ├── core/          # Core configuration
│   ├── db/            # Database models and setup
│   ├── services/      # Business logic
│   └── main.py        # Application entry point
├── alembic/           # Database migrations
└── pyproject.toml     # Dependencies
```


