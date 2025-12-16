# Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone if needed)

## Steps

### 1. Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Backend API (port 8000)
- Frontend (port 3000)

### 2. Initialize Database

```bash
docker-compose exec backend poetry run alembic upgrade head
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Upload Your First OpenAPI Spec

1. Go to http://localhost:3000/upload
2. Select an OpenAPI/Swagger JSON or YAML file
3. Click "Upload and Parse"

### 5. Configure Your Project

1. Click on your project
2. Go to "Configure"
3. Set:
   - Base URL (e.g., `https://api.example.com`)
   - Authentication (if needed)
   - LLM credentials (optional, for AI-enhanced tests)

### 6. Generate Tests

1. Click "Generate Tests"
2. Choose format (Pytest or Postman)
3. Review generated test cases

### 7. Execute Tests

1. Click "Execute Tests"
2. View results in real-time

## Example OpenAPI Spec

Create a file `example.json`:

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Example API",
    "version": "1.0.0"
  },
  "paths": {
    "/users": {
      "get": {
        "operationId": "getUsers",
        "responses": {
          "200": {
            "description": "Success",
            "content": {
              "application/json": {
                "schema": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "id": {"type": "integer"},
                      "name": {"type": "string"}
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

Upload this file to test the system!

## Troubleshooting

### Port Already in Use

Edit `docker-compose.yml` and change ports:
- Frontend: `3000:3000` → `3001:3000`
- Backend: `8000:8000` → `8001:8000`
- Database: `5432:5432` → `5433:5432`

### Database Connection Error

Wait a few seconds for PostgreSQL to start, then retry the migration.

### Frontend Can't Connect to Backend

Check that `REACT_APP_API_URL` in frontend matches backend URL.

## Next Steps

- Read [SETUP.md](SETUP.md) for detailed configuration
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for feature overview

## Need Help?

- API Documentation: http://localhost:8000/docs
- Check logs: `docker-compose logs -f`
- Review error messages in the UI

Happy testing! 🚀




