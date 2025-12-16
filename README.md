# API Test Automation Platform

A comprehensive web application for automated API test generation from Swagger/OpenAPI specifications. Features AI-powered test case generation, security testing, performance testing, and extensible architecture.

## Features

- **OpenAPI/Swagger Parsing**: Automatic parsing and validation of OpenAPI 3.x and Swagger 2.0 specifications
- **$ref Resolution**: Handles schema references and creates reusable collections
- **AI-Powered Test Generation**: Uses LLM with RAG for intelligent test case generation
- **Comprehensive Test Coverage**: 
  - Happy paths
  - Edge cases and boundary values
  - Field validations
  - Security tests (XSS, SQL injection, fuzzing)
  - Performance tests (load simulation)
- **Multiple Output Formats**: Pytest scripts, Postman collections
- **Configurable Runtime**: Base URL, authentication, LLM credentials
- **Modern Stack**: React + TypeScript frontend, FastAPI backend, PostgreSQL with pgvector

## Architecture

```
api-test-gen-app/
├── frontend/          # React + TypeScript UI
├── backend/           # FastAPI Python backend
├── docker-compose.yml # Local development setup
└── docs/              # Documentation
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Using Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5432)
- Backend API (port 8000)
- Frontend (port 3000)

### Manual Setup

#### Backend

```bash
cd backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm start
```

## API Documentation

Once running, visit:
- Backend API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## Configuration

1. Upload your OpenAPI/Swagger JSON file
2. Configure base URL and authentication
3. Set LLM API credentials (OpenAI, xAI, etc.)
4. Generate test cases
5. Execute and view results

## Tech Stack

- **Frontend**: React, TypeScript, Material-UI, Redux Toolkit
- **Backend**: FastAPI, Python 3.11+, Prance, LangChain
- **Database**: PostgreSQL with pgvector
- **Testing**: Pytest, Schemathesis, Locust
- **DevOps**: Docker, GitHub Actions, Prometheus

## License

MIT




