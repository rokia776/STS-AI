# Task Completion Report: API Development, Git Workflow & Docker Deployment

## Part 1: Git & Logging Configuration

### Git Repository Status
The project has a complete git repository with the following commit history:

```
afdf08b (HEAD -> master) Add Docker configuration files for deployment
2e359d2 Switch to local flan-t5 model and remove unused dependencies
531da30 Add POST /api/v1/question endpoint with input validation
b569b7a Add package init files, schemas, and fix root endpoint
adb795d Add DEBUG level for file handler and fix RotatingFileHandler filename
8c56e12 Add rotating file and console logging handlers
c3868cd Improve logging format and timestamp
5074e58 Add basic logging configuration
6f51f96 Initial project setup with uv and FastAPI
```

### Logging Configuration Implementation
**File:** `app/core/logging_config.py`

The logging configuration includes:
- **Log Levels:** DEBUG for file handler, INFO for console handler
- **Formatting:** `%(asctime)s | %(name)s | %(levelname)s | %(message)s` with timestamp format `%Y-%m-%d %H:%M:%S`
- **Output Handling:** 
  - Console handler (StreamHandler) for INFO level logs
  - Rotating file handler (RotatingFileHandler) for DEBUG level logs
  - File rotation: max 200KB per file, 3 backup files
  - Logs stored in `logs/app.log`

### Git Commits for Logging Configuration (Incremental Development)
1. **5074e58** - "Add basic logging configuration"
2. **c3868cd** - "Improve logging format and timestamp"
3. **8c56e12** - "Add rotating file and console logging handlers"
4. **adb795d** - "Add DEBUG level for file handler and fix RotatingFileHandler filename"

### Logging Validation
Logs are being generated correctly as demonstrated in `logs/app.log`:
- Timestamps are properly formatted
- Log levels (INFO, ERROR, WARNING) are correctly applied
- Multiple log entries show successful logging of API requests and responses
- File rotation is configured (though not yet triggered due to file size)

## Part 2: API Development & Validation

### API Endpoint Implementation
**File:** `app/api/v1/question.py`

**Endpoint:** `POST /api/v1/question`

**Features:**
- Accepts JSON payload with `question` field
- Returns structured response with question, answer, and status
- Error handling with appropriate HTTP status codes
- Integration with LLM service for question answering

### Input Validation
**File:** `app/schemas/question.py`

**Validation Rules:**
- Minimum length: 3 characters
- Maximum length: 1000 characters
- Cannot be empty or whitespace only
- Custom field validator to strip whitespace and validate

### API Testing Results

#### Valid Request
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/question" -Method POST -ContentType "application/json" -Body '{"question":"What is FastAPI?"}'
```
**Response:** 200 OK
```json
{
  "question": "What is FastAPI?",
  "answer": "FastAPI () is a standardized protocol for the use of a single cellular network.",
  "status": "success"
}
```

#### Invalid Request - Too Short
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/question" -Method POST -ContentType "application/json" -Body '{"question":"ab"}'
```
**Response:** 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "question"],
      "msg": "String should have at least 3 characters",
      "input": "ab",
      "ctx": {"min_length": 3}
    }
  ]
}
```

#### Invalid Request - Whitespace Only
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/question" -Method POST -ContentType "application/json" -Body '{"question":"   "}'
```
**Response:** 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "question"],
      "msg": "Value error, Question must not be empty or whitespace only",
      "input": " ",
      "ctx": {"error": {}}
    }
  ]
}
```

#### Invalid Request - Empty String
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/question" -Method POST -ContentType "application/json" -Body '{"question":""}'
```
**Response:** 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "question"],
      "msg": "String should have at least 3 characters",
      "input": "",
      "ctx": {"min_length": 3}
    }
  ]
}
```

### API Documentation
The API includes automatic Swagger UI documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Part 3: Technical Questions

### What is a Dockerfile, and what is its purpose?
A Dockerfile is a text document that contains all the commands to assemble a Docker image. It serves as a blueprint for building Docker images, specifying the base image, dependencies, environment variables, file copies, and commands to run the application. The Dockerfile enables reproducible builds and consistent deployment across different environments.

### What is Nginx, and what are its main use cases?
Nginx is a high-performance, open-source web server and reverse proxy server. Its main use cases include:
- **Web Server:** Serving static content (HTML, CSS, JavaScript, images)
- **Reverse Proxy:** Distributing incoming traffic to backend servers
- **Load Balancer:** Distributing traffic across multiple servers
- **API Gateway:** Routing API requests to appropriate services
- **SSL/TLS Termination:** Handling HTTPS encryption/decryption
- **Caching:** Caching content to improve performance
- **WebSocket Proxy:** Handling WebSocket connections

### What is a reverse proxy, and how does it work?
A reverse proxy is a server that sits in front of web servers and forwards client requests to the appropriate backend server. Unlike a forward proxy (which sits in front of clients), a reverse proxy:
- Receives requests from clients
- Forwards requests to one or more backend servers
- Returns the backend server's response to the client
- Provides benefits like load balancing, security, caching, and SSL termination

**How it works:**
1. Client sends request to reverse proxy
2. Reverse proxy analyzes the request
3. Reverse proxy forwards request to appropriate backend server
4. Backend server processes request and sends response to reverse proxy
5. Reverse proxy sends response back to client

### What is the difference between Dockerizing an application and running it inside a Virtual Machine (VM)?

**Docker:**
- Uses containerization technology
- Shares the host OS kernel
- Lightweight (MBs in size)
- Fast startup (seconds)
- Uses layered filesystems
- Less isolation (process-level)
- More efficient resource usage

**Virtual Machine:**
- Uses hardware virtualization
- Has its own complete OS kernel
- Heavyweight (GBs in size)
- Slow startup (minutes)
- Uses full filesystem
- Strong isolation (hardware-level)
- Less efficient resource usage

**Key Difference:** Docker containers are lightweight and share the host OS kernel, while VMs are heavyweight with their own complete OS.

### What is the difference between a Docker image, Docker container, and Docker volume?

**Docker Image:**
- A read-only template for creating containers
- Contains the application code, runtime, libraries, and dependencies
- Built from a Dockerfile
- Can be stored in registries (Docker Hub, private registries)
- Immutable once built

**Docker Container:**
- A runnable instance of a Docker image
- Has a writable layer on top of the image
- Can be started, stopped, and removed
- Isolated process with its own filesystem, network, and process space
- Ephemeral by default (data lost when removed)

**Docker Volume:**
- A persistent storage mechanism for Docker containers
- Exists independently of containers
- Survives container removal/recreation
- Can be shared between multiple containers
- Used for data persistence (databases, logs, user uploads)

**Relationship:** Image → Container (runtime instance) → Volume (persistent storage)

## Part 4: Docker Deployment

### Docker Configuration Files

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY app ./app

ENV FLAN_MODEL=google/flan-t5-small
ENV FLAN_MAX_NEW_TOKENS=128

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
services:
  llm-qa:
    build: .
    image: llm-qa:1.0
    container_name: llm-qa
    ports:
      - "8000:8000"
    environment:
      - FLAN_MODEL=google/flan-t5-small
      - FLAN_MAX_NEW_TOKENS=128
    volumes:
      - ./logs:/app/logs
      - hf_cache:/app/hf_cache

volumes:
  hf_cache:
```

### Docker Operations Status

**Note:** Docker Desktop is currently not running properly (returns 500 Internal Server Error). The following operations need to be performed once Docker Desktop is started:

#### Build Docker Image
```bash
docker-compose build
```

#### Run Container
```bash
docker-compose up -d
```

#### Stop Container
```bash
docker-compose stop
```

#### Remove Container
```bash
docker-compose down
```

#### View Logs
```bash
docker-compose logs -f
```

### Deployment Instructions

1. **Start Docker Desktop** (currently not running)
2. **Build the Docker image:**
   ```bash
   docker-compose build
   ```
3. **Run the container:**
   ```bash
   docker-compose up -d
   ```
4. **Verify the application is running:**
   ```bash
   curl http://localhost:8000/health
   ```
5. **Test the API endpoint:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/question -H "Content-Type: application/json" -d '{"question":"What is Docker?"}'
   ```
6. **View logs:**
   ```bash
   docker-compose logs -f
   ```
7. **Stop the container:**
   ```bash
   docker-compose stop
   ```
8. **Remove the container:**
   ```bash
   docker-compose down
   ```

## Deliverables Summary

### ✅ Completed Deliverables
1. **Git repository with commit history** - 9 commits showing incremental development
2. **Application source code** - Complete FastAPI application with LLM integration
3. **logging_config implementation and validation** - Properly configured with log levels, formatting, and output handling
4. **API endpoint with validation and test evidence** - POST /api/v1/question with comprehensive input validation
5. **Dockerfile and deployment instructions** - Complete Docker configuration files

### ⏳ Pending Deliverables (Requires Docker Desktop)
1. **Screenshots of Docker build, run, stop, and remove operations** - Docker Desktop needs to be started
2. **Application working inside Docker** - Cannot verify without running Docker

### Bonus Deliverables
- ✅ Dockerfile created and configured
- ✅ docker-compose.yml for easy deployment
- ⏳ Docker image build and container run (pending Docker Desktop startup)

## Project Structure
```
LLM-Qa/
├── .dockerignore
├── .env
├── .git/
├── .gitignore
├── .python-version
├── .venv/
├── Dockerfile
├── README.md
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── question.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging_config.py
│   ├── main.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── question.py
│   │   └── response.py
│   └── services/
│       ├── __init__.py
│       └── llm_service.py
├── docker-compose.yml
├── docs/
├── frontend/
├── logs/
│   └── app.log
├── pyproject.toml
├── tests/
└── uv.lock
```

## Conclusion
The project successfully implements a complete LLM Question Answering API with:
- Proper git workflow and version control
- Comprehensive logging configuration with incremental development commits
- RESTful API endpoint with robust input validation
- Docker containerization ready for deployment
- Complete documentation and testing evidence

The only remaining task is to start Docker Desktop and perform the Docker operations to complete the deployment verification.
