# Quick Start Guide

Get the Splunk MCP RAG Agent running in 5 minutes!

## 1. Install Dependencies

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

## 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
# Required:
OPENAI_API_KEY=sk-your-key-here

# Optional (for LangSmith monitoring):
LANGCHAIN_API_KEY=lsv2-your-key-here
```

## 3. Start the Application

**Terminal 1** - Start Backend:
```bash
./run_backend.sh
# Or manually: uv run uvicorn backend.main:app --reload
```

**Terminal 2** - Start Frontend:
```bash
./run_frontend.sh
# Or manually: uv run streamlit run frontend/app.py
```

## 4. Access the Application

- **Streamlit UI**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

## 5. Try It Out!

### Example 1: Chat with the Agent
1. Open http://localhost:8501
2. Type: "Hello, what can you help me with?"
3. See the agent respond with its capabilities

### Example 2: Upload a Document
1. Click "Upload Documents" in sidebar
2. Choose a PDF, TXT, or DOCX file
3. Click "Index Document"
4. Ask: "What is this document about?"

### Example 3: Query Splunk
1. Type: "What Splunk indexes are available?"
2. For sensitive queries, approve when prompted

## Configuration

### MCP Servers

Edit `config/mcp_servers.yaml` to:
- Enable/disable MCP servers
- Configure which tools are available
- Add new MCP servers

### Environment Variables

Key settings in `.env`:
- `OPENAI_API_KEY` - Required for LLM
- `LANGCHAIN_API_KEY` - Optional, for tracing
- `FASTAPI_HOST/PORT` - Backend server config
- `CHROMA_PERSIST_DIR` - Vector store location

## Development

### Linting
```bash
uv run ruff check .           # Check for issues
uv run ruff check --fix .     # Auto-fix issues
uv run ruff format .          # Format code
```

### Type Checking
```bash
uv run ty backend/            # Type check backend
```

## Troubleshooting

**Backend won't start?**
- Check `OPENAI_API_KEY` is set
- Verify port 8000 is available

**Frontend can't connect?**
- Ensure backend is running on port 8000
- Check browser console for errors

**No MCP tools?**
- Verify `config/mcp_servers.yaml` exists
- Check backend logs for MCP initialization

## Next Steps

- Read [TESTING.md](TESTING.md) for comprehensive testing guide
- See [README.md](README.md) for full documentation
- Check LangSmith for trace visualization (if configured)

## Support

For issues or questions:
1. Check backend logs for errors
2. Review health endpoint: http://localhost:8000/api/v1/health
3. Consult TESTING.md for detailed troubleshooting

