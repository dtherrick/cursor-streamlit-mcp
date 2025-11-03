# Testing Guide

This guide provides instructions for testing the Splunk MCP RAG Agent application end-to-end.

## Prerequisites

Before testing, ensure you have:

1. **Installed dependencies**:
   ```bash
   uv sync
   uv sync --dev
   ```

2. **Configured environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys:
   # - OPENAI_API_KEY
   # - LANGCHAIN_API_KEY (optional, for monitoring)
   ```

3. **Verified MCP server access**:
   - Splunk MCP server is configured in your Cursor environment
   - Atlassian MCP server is configured (if using)

## Running the Application

### Option 1: Using Helper Scripts

Terminal 1 - Backend:
```bash
./run_backend.sh
```

Terminal 2 - Frontend:
```bash
./run_frontend.sh
```

### Option 2: Manual Start

Terminal 1 - Backend:
```bash
uv run uvicorn backend.main:app --reload --host localhost --port 8000
```

Terminal 2 - Frontend:
```bash
uv run streamlit run frontend/app.py
```

## End-to-End Testing Scenarios

### 1. Health Check

**Objective**: Verify all components are initialized

**Steps**:
1. Navigate to http://localhost:8501
2. Check the sidebar "System Status" section
3. Verify all components show as "healthy"

**Alternative**:
```bash
curl http://localhost:8000/api/v1/health
```

**Expected Result**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "agent": "healthy",
    "vectorstore": "healthy (0 documents)",
    "document_processor": "healthy"
  }
}
```

### 2. Document Upload and RAG Retrieval

**Objective**: Test document indexing and retrieval

**Steps**:
1. In Streamlit sidebar, click "Upload Documents"
2. Select a test document (PDF, TXT, or DOCX)
3. Click "Index Document"
4. Wait for success message showing number of chunks created
5. In chat, ask a question about the uploaded document
6. Verify the agent uses the `retrieve_documents` tool
7. Verify the response references content from your document

**Example Questions**:
- "What is this document about?"
- "Summarize the main points from the uploaded document"
- "Find information about [specific topic in your document]"

**Expected Behavior**:
- Document is successfully chunked and indexed
- Agent retrieves relevant chunks when asked
- Response contains information from the document

### 3. Splunk Query Execution

**Objective**: Test Splunk MCP integration

**Steps**:
1. In chat, ask: "What Splunk indexes are available?"
2. Verify the agent calls `get_splunk_indexes` tool
3. Observe the response with index information
4. Ask: "Run a Splunk query to search for errors in the last hour"
5. **Important**: This should trigger human-in-the-loop approval

**Expected Behavior**:
- First query (get_splunk_indexes) executes without approval
- Second query (run_splunk_query) requires approval
- Approval UI appears in Streamlit
- You can approve, reject, or edit the query

### 4. Human-in-the-Loop (HITL) Approval

**Objective**: Test sensitive operation approval workflow

**Steps**:
1. Ask: "Search Splunk for failed login attempts in the last 24 hours"
2. Wait for approval request to appear
3. Review the proposed SPL query in the UI
4. Test each approval option:
   - **Approve**: Click "✅ Approve" → Query executes
   - **Reject**: Click "❌ Reject" → Query is cancelled
   - **Edit**: Click "✏️ Edit" → Modify arguments (UI placeholder)

**Expected Behavior**:
- Sensitive Splunk queries trigger approval request
- UI clearly shows what action needs approval
- Approved actions execute and return results
- Rejected actions are cancelled gracefully

### 5. Multi-Turn Conversation

**Objective**: Test conversation persistence and context

**Steps**:
1. Ask: "Upload a document about Python best practices" (if you have one)
2. Ask: "What does it say about error handling?"
3. Ask: "Can you give me more details about that?"
4. Verify the agent maintains context across turns

**Expected Behavior**:
- Agent remembers previous context
- Follow-up questions work correctly
- Conversation thread is maintained

### 6. Combined RAG + MCP Query

**Objective**: Test agent using multiple tools in one conversation

**Steps**:
1. Upload a document about system monitoring
2. Ask: "Based on the document I uploaded, what Splunk query would help monitor the metrics mentioned?"
3. Observe the agent:
   - First retrieves document content
   - Then formulates appropriate Splunk query
   - May request approval for execution

**Expected Behavior**:
- Agent uses retrieve_documents tool first
- Then uses Splunk MCP tools
- Combines information from both sources

### 7. LangSmith Tracing

**Objective**: Verify monitoring and observability

**Steps**:
1. Ensure `LANGCHAIN_API_KEY` is set in `.env`
2. Ensure `LANGCHAIN_TRACING_V2=true`
3. Perform any of the above tests
4. Navigate to https://smith.langchain.com
5. Open your project (default: "splunk-mcp-agent")
6. Verify traces appear for:
   - Chat requests
   - Tool calls (RAG, Splunk)
   - LLM invocations

**Expected Behavior**:
- All agent activities appear in LangSmith
- Traces show full execution flow
- Tool calls are clearly visible

## Testing API Directly

You can also test the API endpoints directly:

### Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What Splunk indexes are available?",
    "thread_id": "test-123"
  }'
```

### Upload Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/document.pdf"
```

### Health Endpoint

```bash
curl http://localhost:8000/api/v1/health
```

## Troubleshooting

### Issue: "Agent not initialized"

**Solution**:
- Check backend logs for initialization errors
- Verify OpenAI API key is set
- Check MCP configuration file exists

### Issue: "Cannot connect to API"

**Solution**:
- Verify backend is running on port 8000
- Check `API_BASE_URL` in Streamlit app
- Review CORS settings if needed

### Issue: "MCP tools not available"

**Solution**:
- Verify `config/mcp_servers.yaml` exists
- Check MCP servers are enabled
- Review backend startup logs for MCP connection errors

### Issue: "Document upload fails"

**Solution**:
- Verify file format is supported (PDF, TXT, DOCX)
- Check file size (very large files may timeout)
- Review backend logs for processing errors

### Issue: "RAG retrieval returns no results"

**Solution**:
- Verify documents have been uploaded
- Check vector store has documents (health endpoint)
- Try more specific queries

## Code Quality Checks

### Linting

```bash
# Run ruff linting
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Checking

```bash
# Run ty type checking
uv run ty backend/
uv run ty frontend/
```

## Success Criteria

The application is working correctly if:

1. ✅ Health check shows all components healthy
2. ✅ Documents can be uploaded and indexed
3. ✅ RAG retrieval finds relevant information
4. ✅ Splunk queries can be executed
5. ✅ Human-in-the-loop approval workflow functions
6. ✅ Conversation state persists across messages
7. ✅ LangSmith traces are visible (if configured)
8. ✅ No critical errors in backend or frontend logs

## Next Steps

After successful testing:

1. **Review LangSmith traces** to understand agent behavior
2. **Test with your own Splunk data** and queries
3. **Upload domain-specific documents** for RAG
4. **Configure additional MCP servers** in YAML config
5. **Explore multi-agent patterns** for future enhancements

