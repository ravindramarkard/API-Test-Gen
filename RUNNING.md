# Project Status - Running

## ✅ Services Status

The API Test Generation Platform is now **running**!

### Running Services

- ✅ **PostgreSQL Database** - Running on port 5432
- ✅ **Backend API (FastAPI)** - Running on port 8000
- ⏳ **Frontend (React)** - Starting on port 3000

## 🌐 Access Points

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics

## 📋 Quick Commands

### View Logs
```bash
docker-compose logs -f          # All services
docker-compose logs -f backend   # Backend only
docker-compose logs -f frontend  # Frontend only
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Rebuild After Code Changes
```bash
docker-compose build
docker-compose up -d
```

## 🗄️ Database Setup

The database tables are automatically created on first startup. To run migrations manually:

```bash
docker-compose exec backend poetry run alembic upgrade head
```

## 🧪 Test the API

### Check Health
```bash
curl http://localhost:8000/health
```

### List Projects
```bash
curl http://localhost:8000/api/v1/projects/
```

### Upload OpenAPI Spec
```bash
curl -X POST http://localhost:8000/api/v1/upload/ \
  -F "file=@your-spec.json" \
  -F "project_name=My Project"
```

## 🐛 Troubleshooting

### Backend Not Starting
- Check logs: `docker-compose logs backend`
- Verify database is healthy: `docker-compose ps`
- Check CORS configuration in `backend/app/core/config.py`

### Frontend Not Starting
- Check logs: `docker-compose logs frontend`
- Verify backend is accessible: `curl http://localhost:8000/health`
- Check REACT_APP_API_URL in frontend environment

### Database Issues
- Verify PostgreSQL is healthy: `docker-compose ps postgres`
- Check connection: `docker-compose exec postgres psql -U apitest -d apitest_db`

## 📝 Next Steps

1. **Access the Frontend**: Open http://localhost:3000 in your browser
2. **Upload an OpenAPI Spec**: Use the upload page to add your first specification
3. **Configure Project**: Set base URL and authentication
4. **Generate Tests**: Create test cases for your API
5. **Execute Tests**: Run tests and view results

## 🎉 Success!

Your API Test Generation Platform is ready to use!


