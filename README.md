# LLM-QA: Question Answering API with Redis Caching

A production-ready FastAPI application that answers questions using an LLM, with PostgreSQL persistence and Redis caching for optimal performance.

## Architecture

The application consists of three services orchestrated by Docker Compose:

- **Backend (FastAPI)**: Handles HTTP requests, generates answers using FLAN-T5 model, manages caching logic
- **PostgreSQL**: Stores Q&A history with UUID primary keys and indexed timestamps
- **Redis**: Provides in-memory caching with 1-hour TTL to reduce LLM calls

### Technology Stack

- **Python 3.11** with FastAPI
- **PostgreSQL 15** for persistent storage
- **Redis 7** for caching
- **SQLAlchemy** (via asyncpg) for database operations
- **Docker & Docker Compose** for containerization
- **GitHub Actions** for CI/CD

### Database Schema

The `questions` table stores Q&A pairs with the following design:

```sql
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'success',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_questions_created_at ON questions(created_at DESC);
```

**Design Decisions:**

- **UUID primary key**: Prevents ID enumeration attacks and supports distributed systems
- **Single table for Q&A**: Simple one-to-one relationship doesn't justify separate tables
- **Index on created_at**: Enables efficient sorting for history retrieval
- **Original question storage**: Preserves exact user input for accuracy

## How Caching Works

The application implements a cache-aside pattern:

1. **User submits a question**
2. **Check Redis** for cached answer using key `question:{question_text}`
3. **Cache HIT**: Return cached answer immediately (no LLM call, no DB write)
4. **Cache MISS**: 
   - Generate answer using FLAN-T5 model
   - Save Q&A to PostgreSQL
   - Cache answer in Redis with 1-hour TTL
   - Return answer to user

**Duplicate Question Strategy**: The application creates a new PostgreSQL record for each submission to track usage history, but returns cached answers when available. This balances analytics needs with performance.

## Environment Variables

Configure these in `.env` or docker-compose.yml:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLAN_MODEL` | `google/flan-t5-small` | Hugging Face model to use |
| `FLAN_MAX_NEW_TOKENS` | `256` | Maximum tokens for answer generation |
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/llm_qa` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |

## Running the Project

### Prerequisites

- Docker and Docker Compose installed
- Git

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd LLM-Qa
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

   This will:
   - Build the backend image (multi-stage build)
   - Start PostgreSQL with health checks
   - Start Redis with health checks
   - Start backend after dependencies are healthy

3. **Verify the application**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Test the API**
   ```bash
   curl -X POST http://localhost:8000/api/v1/question \
     -H "Content-Type: application/json" \
     -d '{"question":"What is Docker?"}'
   ```

5. **View logs**
   ```bash
   docker-compose logs -f llm-qa
   ```

6. **Stop services**
   ```bash
   docker-compose down
   ```

### Data Persistence

PostgreSQL and Redis use named volumes for persistence:
- `postgres_data`: Database data survives container restarts
- `redis_data`: Redis cache data survives container restarts
- `hf_cache`: Hugging Face model cache to avoid re-downloading

## Docker Implementation Details

### Multi-Stage Build

The Dockerfile uses two stages:

**Build Stage:**
- Installs uv package manager
- Copies dependency files and installs packages
- Builds the application
- Includes compilers and dev dependencies

**Runtime Stage:**
- Starts from fresh python:3.11-slim image
- Creates non-root user `appuser`
- Copies only necessary artifacts from builder
- Runs application as non-root user
- Smaller image size, improved security

### Non-Root User

The container runs as `appuser` for security:
- Prevents privilege escalation attacks
- Limits damage if container is compromised
- Follows security best practices

### Health Checks

PostgreSQL and Redis include health checks:
- PostgreSQL: Uses `pg_isready` to verify database is accepting connections
- Redis: Uses `redis-cli ping` to verify server is responding
- Backend waits for healthy dependencies before starting

### Container Networking

Services communicate using Docker Compose network:
- Backend connects to `postgres:5432` (not localhost)
- Backend connects to `redis:6379` (not localhost)
- PostgreSQL and Redis ports are NOT published to host (security)
- Only backend port 8000 is exposed

## GitHub Actions CI/CD

### Workflow Overview

The `.github/workflows/docker-build-push.yml` workflow:

1. **Triggers** on push to `main` or `feature/docker-improvements` branches
2. **Checks out** the repository code
3. **Sets up** Docker Buildx for multi-platform builds
4. **Authenticates** with Docker Hub using secrets
5. **Extracts metadata** for image tagging (branch name, commit SHA, latest)
6. **Builds and pushes** the Docker image to Docker Hub
7. **Uses GitHub Actions cache** to speed up builds

### Required GitHub Secrets

Configure these in your repository settings:

- `DOCKERHUB_USERNAME`: Your Docker Hub username
- `DOCKERHUB_TOKEN`: Docker Hub access token (create in Docker Hub account settings)

### Image Tags

Images are tagged as:
- `<username>/llm-qa:main` or `:<branch-name>` for branch builds
- `<username>/llm-qa:<branch>-<commit-sha>` for specific commits
- `<username>/llm-qa:latest` for main branch

### Pulling and Running the Published Image

After the workflow runs, pull and run:

```bash
docker pull YOUR_USERNAME/llm-qa:latest

docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e REDIS_URL=redis://host:6379/0 \
  YOUR_USERNAME/llm-qa:latest
```

Note: For full functionality, run with Docker Compose to include PostgreSQL and Redis.

## API Endpoints

### POST /api/v1/question

Submit a question and get an answer.

**Request:**
```json
{
  "question": "What is FastAPI?"
}
```

**Response (Cache MISS):**
```json
{
  "question": "What is FastAPI?",
  "answer": "FastAPI is a modern web framework...",
  "status": "success"
}
```

**Response (Cache HIT):**
```json
{
  "question": "What is FastAPI?",
  "answer": "FastAPI is a modern web framework...",
  "status": "success (cached)"
}
```

### GET /api/v1/stats

Get system statistics.

**Response:**
```json
{
  "total_questions_processed": 42,
  "api_version": "1.0.0",
  "status": "operational"
}
```

### GET /api/v1/questions

Get question history.

**Query Parameters:**
- `limit` (default: 100) - Maximum number of questions to return

**Response:**
```json
{
  "count": 10,
  "questions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "question": "What is Docker?",
      "answer": "Docker is a containerization platform...",
      "status": "success",
      "created_at": "2026-11-12T12:00:00"
    }
  ]
}
```

## Testing the API

### Test Cache Hit/Miss

1. **First request (MISS):**
   ```bash
   curl -X POST http://localhost:8000/api/v1/question \
     -H "Content-Type: application/json" \
     -d '{"question":"What is Redis?"}'
   ```
   Response status: `"success"`

2. **Second request (HIT):**
   ```bash
   curl -X POST http://localhost:8000/api/v1/question \
     -H "Content-Type: application/json" \
     -d '{"question":"What is Redis?"}'
   ```
   Response status: `"success (cached)"`

3. **Wait 1 hour (TTL expires)**
4. **Third request (MISS again):**
   Response status: `"success"`

### Test Database Persistence

```bash
# Submit a question
curl -X POST http://localhost:8000/api/v1/question \
  -H "Content-Type: application/json" \
  -d '{"question":"Test persistence"}'

# Retrieve history
curl http://localhost:8000/api/v1/questions
```

### Test Container Restart Persistence

```bash
# Submit a question
curl -X POST http://localhost:8000/api/v1/question \
  -H "Content-Type: application/json" \
  -d '{"question":"Test restart"}'

# Restart containers
docker-compose restart

# Verify data persists
curl http://localhost:8000/api/v1/questions
```

## Project Structure

```
LLM-Qa/
├── .github/
│   └── workflows/
│       └── docker-build-push.yml    # CI/CD workflow
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── question.py           # API endpoints
│   ├── core/
│   │   ├── config.py                 # Configuration
│   │   ├── database.py               # PostgreSQL connection
│   │   ├── logging_config.py         # Logging setup
│   │   └── redis_cache.py            # Redis operations
│   ├── main.py                       # FastAPI app
│   ├── models/
│   │   └── question.py               # Database models
│   ├── schemas/
│   │   ├── question.py               # Request schemas
│   │   └── response.py               # Response schemas
│   └── services/
│       ├── flan_backend.py           # FLAN-T5 integration
│       └── llm_service.py            # LLM service
├── logs/
│   └── app.log                       # Application logs
├── Dockerfile                        # Multi-stage build
├── docker-compose.yml                # Service orchestration
├── pyproject.toml                    # Dependencies
└── uv.lock                           # Locked dependencies
```

## Bonus Challenges (Optional)

These features can be added for extra credit:

- [ ] Background worker for async Q&A generation
- [ ] Scheduler for deleting old records
- [ ] Redis as message broker for background jobs
- [ ] Endpoint to clear Redis cache
- [ ] Automated tests for cache hits/misses
- [ ] CI test job before Docker image publishing
- [ ] Semantic caching for similar questions

## Troubleshooting

### Container won't start

Check health checks:
```bash
docker-compose ps
docker-compose logs postgres
docker-compose logs redis
```

### Redis connection errors

The API handles Redis failures gracefully and falls back to PostgreSQL. Check Redis logs:
```bash
docker-compose logs redis
```

### Database connection errors

Verify PostgreSQL is healthy:
```bash
docker-compose exec postgres pg_isready -U postgres -d llm_qa
```

### Permission errors with volumes

The non-root user should have correct permissions. If issues occur:
```bash
docker-compose down -v
docker-compose up -d
```

## License

MIT
