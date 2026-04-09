# Claude Agent

An enterprise-grade AI Agent service built with FastAPI and LangChain, powered by Anthropic Claude SDK.

## Features

- **RESTful API**: FastAPI-based service with health checks and chat endpoints
- **Tool Execution**: Built-in tools for bash commands, file operations, and HTTP requests
- **Session Management**: Persistent conversation sessions with SQLite storage
- **Streaming Support**: Server-Sent Events (SSE) for real-time responses
- **Skill System**: Reusable skill modules for complex tasks (e.g., code review)
- **MCP Integration**: Model Context Protocol for external resource access
- **Docker Ready**: Containerized deployment with Docker Compose

## Requirements

- Python 3.10 or higher
- Anthropic API key

## Quick Start

### 1. Clone and Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Start the Service

```bash
# Run with Python
python -m backend

# Or with uvicorn (with auto-reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up --build
```

### 4. Verify the Service

```bash
# Health check
curl http://localhost:8000/health
# {"status": "ok"}
```

## Basic Usage

### Chat API (Non-streaming)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "List files in the current directory"}'
```

### Response Example

```json
{
  "session_id": "xxx",
  "message": "Let me list the files for you...",
  "tool_calls": [
    {"name": "bash", "input": {"cmd": "ls"}, "output": "..."}
  ]
}
```

### Chat API (Streaming)

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "Analyze this project"}'
```

### Using Skills

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message": "Review the code", "skill": "code_review"}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/chat` | POST | Chat (non-streaming) |
| `/api/chat/stream` | POST | Chat (streaming SSE) |
| `/api/sessions` | GET/POST | Session management |
| `/api/tools` | GET | List available tools |
| `/api/skills` | GET | List available skills |

## Documentation

- [Architecture Design](docs/ARCHITECTURE.md) - Technical architecture and design decisions
- [Development Roadmap](docs/ROADMAP.md) - Development phases and milestones

## Development

### Running Tests

```bash
pytest
```

### Code Linting

```bash
# Check for issues
ruff check .

# Format code
ruff format .
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_BASE_URL` | Custom API base URL | - |
| `MODEL_ID` | Claude model to use | `claude-sonnet-4-6-20250514` |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Agent | LangChain + LangGraph |
| Database | SQLite / PostgreSQL |
| Deployment | Docker |
| Authentication | API Key |

## License

This project is provided as-is for educational and development purposes.

## Acknowledgments

Built with:
- [Anthropic Claude SDK](https://github.com/anthropics/anthropic-sdk-python)
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangChain](https://github.com/langchain-ai/langchain)
