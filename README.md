# Splunk MCP-Enabled RAG Agent Platform

A production-ready LangGraph agent application with Streamlit frontend, FastAPI backend, RAG capabilities using ChromaDB, MCP server integration (Splunk + Atlassian), and LangSmith monitoring for Splunk data interaction and document-based Q&A.

## Architecture

- **Frontend**: Streamlit UI for chat interface and document upload
- **Backend**: FastAPI server handling business logic and LangGraph orchestration
- **Agent Layer**: LangGraph agent with RAG, MCP tool calling, and human-in-the-loop support

## Features

- ✅ General-purpose chat with OpenAI GPT-4
- ✅ Document upload and RAG-based retrieval (PDF, TXT, DOCX)
- ✅ Splunk MCP integration for SPL queries
- ✅ Atlassian MCP integration
- ✅ Human-in-the-loop for sensitive operations
- ✅ LangSmith tracing and monitoring
- ✅ Configuration-based MCP server loading
- ✅ Conversation thread persistence

## Prerequisites

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) for package management
- OpenAI API key
- LangSmith API key (optional, for monitoring)
- Access to Splunk and Atlassian MCP servers

## Quick Start

### 1. Install dependencies

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
uv sync --dev  # Include development dependencies
```

### 2. Configure environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys and configuration
```

### 3. Configure MCP servers

Edit `config/mcp_servers.json` to configure your Splunk and Atlassian MCP server connections.

### 4. Run the application

Assuming you are in the project root:
```bash
# Terminal 1: Start FastAPI backend
./scripts/run_backend.sh
-or-
uv run uvicorn backend.main:app --reload --host localhost --port 8000

# Terminal 2: Start Streamlit frontend
./scripts/run_frontend.sh
-or-
uv run streamlit run frontend/app.py
```

### 5. Access the application

- **Streamlit UI**: http://localhost:8501
- **FastAPI Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Development

### Linting and Formatting

```bash
# Run ruff linting
uvx ruff check

# Auto-fix issues
uvx ruff check --fix

# Format code
uvx ruff format
```

### Type Checking

```bash
# Run type checking with ty
uvx ty backend/
uvx ty frontend/
```

## Project Structure

```
.
├── backend/
│   ├── main.py                    # FastAPI application entry point
│   ├── agent/
│   │   ├── graph.py               # LangGraph agent definition
│   │   ├── state.py               # Agent state models
│   │   └── tools.py               # MCP and RAG tools
│   ├── rag/
│   │   ├── vectorstore.py         # ChromaDB integration
│   │   └── document_processor.py # Document loading and chunking
│   ├── mcp/
│   │   ├── server_manager.py     # MCP server connection manager
│   │   └── config.py              # MCP server configuration loader
│   └── api/
│       └── routes.py              # FastAPI endpoints
├── frontend/
│   └── app.py                     # Streamlit application
├── config/
│   └── mcp_servers.json           # MCP server configurations
├── data/
│   ├── uploads/                   # User document uploads
│   ├── chroma_db/                 # ChromaDB persistence
│   └── checkpoints/               # Conversation state checkpoints
├── scripts/
│   ├── run_backend.sh             # Backend startup script
│   └── run_frontend.sh            # Frontend startup script
├── docs/
│   ├── TESTING.md                 # Testing guide and scenarios
│   ├── QUICKSTART.md              # Quick start guide
│   ├── IMPLEMENTATION_SUMMARY.md  # Technical implementation details
│   ├── MCP_INTEGRATION_NOTES.md   # MCP server integration guide
│   ├── TYPE_CHECKING_NOTES.md     # Type checking with ty
│   ├── CHANGES_SUMMARY.md         # Recent changes log
│   └── SLASH_COMMANDS.md          # Chat slash commands reference
├── pyproject.toml
├── .env.example
└── README.md
```

## License

MIT

