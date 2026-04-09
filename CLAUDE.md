# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Agent is an enterprise-grade AI Agent service built with:
- **Python 3.10+** with FastAPI framework
- **LangChain + LangGraph** for agent orchestration
- **Anthropic Claude SDK** for LLM capabilities
- **Docker** for containerized deployment

The service provides RESTful APIs for conversational AI with tool execution capabilities.

## Directory Structure

```
claude-agent/
├── backend/                 # Backend source code
│   ├── __init__.py
│   ├── __main__.py          # Module entry point
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration management
│   ├── agent.py             # Native Agent implementation
│   ├── langchain_agent.py   # LangChain Agent implementation
│   ├── tools.py             # Tool definitions
│   ├── api/                 # API routes
│   │   └── __init__.py
│   ├── db/                  # Database layer
│   │   ├── __init__.py
│   │   └── database.py
│   └── middleware/          # Middleware (auth, etc.)
│       ├── __init__.py
│       └── auth.py
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md      # Architecture design
│   └── ROADMAP.md           # Development roadmap
├── data/                    # Data directory (gitignore)
├── tests/                   # Test files
├── pyproject.toml           # Project configuration
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker compose configuration
└── .env.example             # Environment variables template
```

## Common Commands

```bash
# Setup virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start the development server
python -m backend

# Or using uvicorn directly
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker
docker-compose up --build

# Run tests
pytest

# Run linting
ruff check .

# Format code
ruff format .
```

## Important Rules

**When making any updates or iterations to the codebase, you MUST synchronously update the related documentation in `docs/`:**

- If modifying architecture or adding new components, update `docs/ARCHITECTURE.md`
- If changing development plans or adding new features, update `docs/ROADMAP.md`
- Keep documentation in sync with code changes

## Architecture

For detailed architecture design, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Key components:
- **API Gateway (FastAPI)**: Authentication, rate limiting, logging, routing
- **Agent Core**: LangGraph workflow (Router -> Agent -> Output)
- **Tools/Skills/MCP**: Extensible capability system
- **Storage**: SQLite (development) / PostgreSQL (production)

## Development Roadmap

For development plans and milestones, see [docs/ROADMAP.md](docs/ROADMAP.md)

## Configuration

Required environment variables:
- `ANTHROPIC_API_KEY`: Your Anthropic API key

Optional configuration:
- `ANTHROPIC_BASE_URL`: Custom base URL for API providers
- `MODEL_ID`: Model to use (defaults to `claude-sonnet-4-6-20250514`)

Copy `.env.example` to `.env` and configure your settings.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Agent | LangChain + LangGraph |
| Database | SQLite -> PostgreSQL |
| Deployment | Docker |
| Authentication | API Key |
| Linting | ruff (line-length: 100, target: py310) |
| Testing | pytest |
