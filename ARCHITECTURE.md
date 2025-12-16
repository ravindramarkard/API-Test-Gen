# Architecture Overview

## System Architecture

The API Test Generation Platform follows a modular, microservices-inspired architecture with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  - Dashboard, Upload, Configuration, Results Views          │
│  - Redux for State Management                              │
│  - Material-UI Components                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────────┐
│                  Backend API (FastAPI)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Upload     │  │   Config     │  │   Generate   │     │
│  │   Endpoint   │  │   Endpoint   │  │   Endpoint   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│  ┌──────▼─────────────────▼─────────────────▼───────┐     │
│  │           Service Layer                           │     │
│  │  - OpenAPI Parser (with $ref resolution)         │     │
│  │  - Test Generator (Baseline + LLM)               │     │
│  │  - Test Executor                                 │     │
│  └──────────────────────────────────────────────────┘     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼─────┐ ┌────▼──────┐
│  PostgreSQL  │ │   Redis   │ │   LLM API │
│  (pgvector)  │ │  (Celery) │ │  (OpenAI) │
└──────────────┘ └───────────┘ └───────────┘
```

## Component Details

### Frontend Layer

**Technology Stack:**
- React 18 with TypeScript
- Material-UI for components
- Redux Toolkit for state management
- React Router for navigation
- Axios for API communication

**Key Components:**
- `Dashboard`: Project listing and overview
- `Upload`: OpenAPI/Swagger file upload
- `ProjectDetail`: Project details and test generation
- `Config`: Runtime configuration (base URL, auth, LLM)
- `Results`: Test execution results visualization

### Backend API Layer

**Technology Stack:**
- FastAPI (async Python web framework)
- SQLAlchemy ORM
- Alembic for migrations
- Pydantic for validation

**API Endpoints:**
- `POST /api/v1/upload/`: Upload and parse OpenAPI spec
- `GET /api/v1/projects/`: List all projects
- `GET /api/v1/projects/{id}`: Get project details
- `POST /api/v1/config/{project_id}`: Save project configuration
- `POST /api/v1/generate/{project_id}`: Generate test cases
- `POST /api/v1/execute/{test_suite_id}`: Execute test suite
- `GET /api/v1/execute/{execution_id}`: Get execution results

### Service Layer

#### OpenAPI Parser
- Parses OpenAPI 3.x and Swagger 2.0 specifications
- Resolves `$ref` references using Prance
- Extracts endpoints, parameters, schemas
- Creates reusable schema collections

#### Test Generator
**Baseline Generation:**
- Uses Schemathesis for property-based testing
- Generates happy path tests
- Creates validation tests (required fields, types)
- Boundary value testing

**LLM-Enhanced Generation:**
- Integrates with OpenAI/xAI/Anthropic APIs
- Uses RAG (Retrieval-Augmented Generation) for context
- Generates security tests (XSS, SQL injection)
- Creates edge case scenarios
- Performance test suggestions

#### Test Executor
- Executes HTTP requests against configured base URL
- Supports multiple authentication methods
- Tracks test results and metrics
- Handles errors gracefully

### Data Layer

**PostgreSQL Database:**
- `users`: User accounts
- `projects`: OpenAPI specifications
- `project_configs`: Runtime configurations (encrypted)
- `test_suites`: Generated test cases
- `test_executions`: Execution results

**pgvector Extension:**
- Stores vector embeddings for RAG
- Enables semantic search over schemas

### External Integrations

**LLM Providers:**
- OpenAI (GPT-4, GPT-3.5)
- xAI (Grok models)
- Anthropic (Claude)
- Custom endpoints supported

**Authentication Methods:**
- Basic Auth (username/password)
- Bearer Token
- API Key

## Data Flow

### Test Generation Flow

1. User uploads OpenAPI spec → Backend validates and parses
2. User configures base URL, auth, LLM credentials
3. User triggers test generation:
   - Parser extracts endpoints and schemas
   - Baseline generator creates basic tests
   - LLM generator creates enhanced tests (if configured)
   - Tests stored in database
4. User executes tests:
   - Executor runs tests against API
   - Results stored and visualized

### Security Considerations

- **Encryption**: Sensitive credentials encrypted using Fernet
- **Input Validation**: All inputs validated via Pydantic
- **SQL Injection**: Protected by SQLAlchemy ORM
- **CORS**: Configurable CORS origins
- **Rate Limiting**: Can be added via middleware

## Scalability

**Horizontal Scaling:**
- Stateless API design
- Database connection pooling
- Redis for task queue (Celery)
- Load balancer ready

**Performance Optimizations:**
- Async request handling
- Background task processing
- Caching of parsed specs
- Batch LLM API calls

## Monitoring & Observability

- **Logging**: Structured logging with rotation
- **Metrics**: Prometheus metrics endpoint
- **Error Tracking**: Sentry integration (optional)
- **Health Checks**: `/health` endpoint

## Extensibility

**Plugin System:**
- Modular service architecture
- Easy to add new test types
- Custom LLM providers
- Additional output formats

**Future Enhancements:**
- OAuth2 authentication
- Multi-user support with permissions
- Test scheduling and CI/CD integration
- Advanced security scanning (OWASP ZAP)
- Performance testing with Locust
- Custom test templates




