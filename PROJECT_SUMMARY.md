# API Test Generation Platform - Project Summary

## Overview

A comprehensive full-stack web application for automated API test generation from OpenAPI/Swagger specifications. The platform combines rule-based test generation with AI-powered LLM integration to create comprehensive test suites covering happy paths, edge cases, security, and performance scenarios.

## Key Features

✅ **OpenAPI/Swagger Parsing**
- Supports OpenAPI 3.x and Swagger 2.0
- Automatic $ref resolution
- Schema collection extraction
- Endpoint discovery

✅ **Test Generation**
- Baseline tests (Schemathesis-based)
- AI-enhanced tests (LLM with RAG)
- Multiple test types:
  - Happy paths
  - Edge cases
  - Boundary values
  - Field validations
  - Security tests (XSS, SQL injection)
  - Performance tests

✅ **Multiple Output Formats**
- Pytest scripts
- Postman collections

✅ **Test Execution**
- Real-time execution
- Results tracking
- Pass/fail statistics
- Error reporting

✅ **Configuration Management**
- Base URL configuration
- Multiple auth methods (Basic, Bearer, API Key)
- LLM provider configuration
- Encrypted credential storage

✅ **Modern UI**
- React + TypeScript
- Material-UI components
- Real-time updates
- Responsive design

## Project Structure

```
latestApi/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Configuration, security, logging
│   │   ├── db/             # Database models
│   │   └── services/       # Business logic
│   ├── alembic/            # Database migrations
│   └── tests/              # Test suite
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API services
│   │   └── store/          # Redux store
├── docker-compose.yml      # Docker orchestration
└── .github/workflows/      # CI/CD pipelines
```

## Technology Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL with pgvector
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Parsing**: Prance, openapi-spec-validator
- **Testing**: Schemathesis, Pytest
- **LLM**: LangChain (OpenAI, xAI, Anthropic)
- **Task Queue**: Celery + Redis
- **Monitoring**: Prometheus, Sentry

### Frontend
- **Framework**: React 18
- **Language**: TypeScript
- **UI Library**: Material-UI
- **State Management**: Redux Toolkit
- **HTTP Client**: Axios
- **Routing**: React Router

### DevOps
- **Containerization**: Docker
- **CI/CD**: GitHub Actions
- **Database**: PostgreSQL 16 with pgvector

## Getting Started

### Quick Start (Docker)

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend poetry run alembic upgrade head

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

### Manual Setup

See [SETUP.md](SETUP.md) for detailed instructions.

## API Endpoints

### Upload & Projects
- `POST /api/v1/upload/` - Upload OpenAPI spec
- `GET /api/v1/projects/` - List projects
- `GET /api/v1/projects/{id}` - Get project details

### Configuration
- `POST /api/v1/config/{project_id}` - Save configuration
- `GET /api/v1/config/{project_id}` - Get configuration

### Test Generation & Execution
- `POST /api/v1/generate/{project_id}` - Generate tests
- `POST /api/v1/execute/{test_suite_id}` - Execute tests
- `GET /api/v1/execute/{execution_id}` - Get results

## Usage Workflow

1. **Upload Specification**
   - Navigate to Upload page
   - Select OpenAPI/Swagger JSON or YAML file
   - System parses and validates the spec

2. **Configure Project**
   - Set base URL for your API
   - Configure authentication
   - Set LLM credentials (optional, for AI-enhanced tests)

3. **Generate Tests**
   - Click "Generate Tests"
   - Choose output format
   - Review generated test cases

4. **Execute Tests**
   - Click "Execute Tests"
   - Monitor real-time progress
   - Review results and statistics

## Security Features

- Encrypted credential storage (Fernet)
- Input validation (Pydantic)
- SQL injection protection (ORM)
- CORS configuration
- Secure password hashing (bcrypt)

## Monitoring & Observability

- Structured logging with rotation
- Prometheus metrics endpoint (`/metrics`)
- Health check endpoint (`/health`)
- Error tracking (Sentry integration ready)

## Extensibility

The platform is designed for extensibility:

- **New Test Types**: Add custom test generators
- **LLM Providers**: Support for custom LLM endpoints
- **Output Formats**: Easy to add new formats
- **Authentication**: Plugin system for new auth methods

## Future Enhancements

- [ ] User authentication and multi-tenancy
- [ ] Test scheduling and CI/CD integration
- [ ] Advanced security scanning (OWASP ZAP)
- [ ] Performance testing with Locust
- [ ] Custom test templates
- [ ] Test history and comparison
- [ ] Team collaboration features
- [ ] API documentation generation

## Development

### Running Tests

```bash
# Backend
cd backend
poetry run pytest

# Frontend
cd frontend
npm test
```

### Code Quality

```bash
# Backend
poetry run black .
poetry run ruff check .

# Frontend
npm run lint
```

## Documentation

- [README.md](README.md) - Main documentation
- [SETUP.md](SETUP.md) - Setup instructions
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture details
- [backend/README.md](backend/README.md) - Backend documentation
- [frontend/README.md](frontend/README.md) - Frontend documentation

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Check API documentation at `/docs` endpoint
- Review setup guides
- Open an issue on GitHub

---

Built with ❤️ using FastAPI, React, and modern best practices.




