# Setup Guide

Complete setup instructions for the API Test Generation Platform.

## Prerequisites

- Docker and Docker Compose (recommended)
- OR Node.js 18+ and Python 3.11+ for local development
- PostgreSQL 16+ with pgvector extension (if not using Docker)

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd latestApi
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Database: localhost:5432

4. **Run database migrations** (first time only)
   ```bash
   docker-compose exec backend poetry run alembic upgrade head
   ```

## Manual Setup

### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Install Poetry** (if not installed)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies**
   ```bash
   poetry install
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up PostgreSQL with pgvector**
   ```bash
   # Using Docker
   docker run -d \
     --name postgres-apitest \
     -e POSTGRES_USER=apitest \
     -e POSTGRES_PASSWORD=apitest123 \
     -e POSTGRES_DB=apitest_db \
     -p 5432:5432 \
     pgvector/pgvector:pg16
   ```

6. **Run migrations**
   ```bash
   poetry run alembic upgrade head
   ```

7. **Start the server**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API URL
   ```

4. **Start the development server**
   ```bash
   npm start
   ```

## Configuration

### Backend Configuration

Edit `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SECRET_KEY=your-secret-key-min-32-characters
ENCRYPTION_KEY=auto-generated-on-first-run
CORS_ORIGINS=http://localhost:3000
REDIS_URL=redis://localhost:6379/0
```

### Frontend Configuration

Edit `frontend/.env`:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Usage

1. **Upload OpenAPI Specification**
   - Go to http://localhost:3000/upload
   - Select your OpenAPI/Swagger JSON or YAML file
   - Click "Upload and Parse"

2. **Configure Project**
   - Set base URL for your API
   - Configure authentication (Basic, Bearer, API Key)
   - Set LLM credentials for AI-enhanced test generation

3. **Generate Tests**
   - Click "Generate Tests" on the project page
   - Choose output format (Pytest or Postman)
   - Review generated test cases

4. **Execute Tests**
   - Click "Execute Tests"
   - View results in real-time
   - Review pass/fail statistics

## Development

### Running Tests

**Backend:**
```bash
cd backend
poetry run pytest
```

**Frontend:**
```bash
cd frontend
npm test
```

### Code Formatting

**Backend:**
```bash
cd backend
poetry run black .
poetry run ruff check .
```

**Frontend:**
```bash
cd frontend
npm run lint
```

### Database Migrations

**Create migration:**
```bash
cd backend
poetry run alembic revision --autogenerate -m "description"
```

**Apply migrations:**
```bash
poetry run alembic upgrade head
```

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running
- Check DATABASE_URL in .env
- Verify pgvector extension is installed: `CREATE EXTENSION vector;`

### Port Conflicts

- Change ports in `docker-compose.yml` if 3000, 8000, or 5432 are in use
- Update CORS_ORIGINS if using different ports

### LLM Integration Issues

- Verify API keys are correct
- Check LLM provider endpoint URLs
- Ensure sufficient API credits/quota

### Frontend Not Connecting to Backend

- Verify REACT_APP_API_URL in frontend/.env
- Check CORS_ORIGINS in backend/.env
- Ensure backend is running

## Production Deployment

1. **Set secure environment variables**
   - Generate strong SECRET_KEY and ENCRYPTION_KEY
   - Use production database
   - Configure proper CORS origins

2. **Build frontend**
   ```bash
   cd frontend
   npm run build
   ```

3. **Use production WSGI server**
   ```bash
   cd backend
   poetry run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

4. **Set up reverse proxy** (nginx, etc.)
   - Serve frontend static files
   - Proxy API requests to backend

5. **Enable monitoring**
   - Configure Sentry DSN
   - Set up Prometheus/Grafana
   - Enable logging aggregation

## Support

For issues and questions, please check:
- API Documentation: http://localhost:8000/docs
- Backend README: `backend/README.md`
- Frontend README: `frontend/README.md`




