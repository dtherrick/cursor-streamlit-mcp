# Recent Changes Summary

## MCP Integration Update

### What Changed

Completely rewrote the MCP integration to work with **remote MCP servers** using the MCP protocol specification (JSON-RPC over stdin/stdout).

### Key Changes

1. **Configuration Format: YAML → JSON**
   - Changed from `config/mcp_servers.yaml` to `config/mcp_servers.json`
   - Matches standard MCP server configuration format
   - Supports environment variable substitution with `${VAR_NAME}` syntax

2. **MCP Server Manager Rewrite**
   - Now spawns actual `npx mcp-remote` processes
   - Implements MCP protocol (JSON-RPC 2.0)
   - Protocol handshake: initialize → initialized → tools/list → tools/call
   - Real-time communication with remote MCP servers

3. **Configuration Example**
   ```json
   {
     "mcpServers": {
       "splunk-mcp": {
         "command": "npx",
         "args": [
           "-y",
           "mcp-remote",
           "https://cloud-architects.api.scs.splunk.com/cloud-architects/mcp/v1/",
           "--header",
           "Content-Type: application/json",
           "--header",
           "Authorization: Bearer ${SPLUNK_MCP_TOKEN}"
         ],
         "enabled": false
       }
     }
   }
   ```

4. **Environment Variables**
   - Added `SPLUNK_MCP_TOKEN` to `.env.example`
   - Configuration automatically substitutes env vars

5. **Tool Naming Convention**
   - MCP tools are prefixed with server name
   - Format: `{server_name}_{tool_name}`
   - Example: `splunk-mcp_run_splunk_query`

### How to Enable

1. **Add your Splunk MCP token to `.env`:**
   ```env
   SPLUNK_MCP_TOKEN=your-bearer-token-here
   ```

2. **Enable servers in `config/mcp_servers.json`:**
   ```json
   {
     "mcpServers": {
       "splunk-mcp": {
         "enabled": true,  // Change to true
         ...
       }
     }
   }
   ```

3. **Uncomment MCP initialization in `backend/main.py`** (lines 72-83)

4. **Ensure Node.js is installed:**
   ```bash
   node --version  # Should show v16+ 
   ```

5. **Restart backend:**
   ```bash
   ./run_backend.sh
   ```

### Documentation

See `MCP_INTEGRATION_NOTES.md` for:
- Detailed protocol explanation
- Troubleshooting guide
- Adding new MCP servers
- Testing MCP connections manually

## Other Recent Fixes

### Environment Variable Loading
- Added `python-dotenv` to automatically load `.env` file
- Backend now loads environment variables at startup

### Checkpointing
- Switched from SQLite to MemorySaver (in-memory)
- Conversation state persists during runtime but not across restarts
- Simpler setup, no file permissions issues

### Development Tools
- Added `watchdog` to dev dependencies for better Streamlit auto-reload
- Both `ty` and `ruff` pass with zero errors

### MCP Integration Status
- ✅ Configuration structure ready
- ✅ Protocol implementation complete
- ✅ Tool conversion working
- ⏸️  Currently disabled for testing
- 📝 Enable when ready to use actual MCP servers

## Next Steps

1. Verify basic application works (RAG + chat)
2. Add Splunk MCP token to `.env`
3. Enable MCP servers when ready
4. Test Splunk queries through the agent

