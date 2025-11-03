# MCP Integration Guide

## Overview

This application integrates with **remote MCP servers** using the MCP (Model Context Protocol) specification. The servers are accessed via `npx mcp-remote` which spawns processes that communicate using JSON-RPC.

## Configuration

### MCP Server Configuration File

Edit `config/mcp_servers.json` to configure your MCP servers:

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
      "enabled": true
    },
    "atlassian": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://mcp.atlassian.com/v1/sse"
      ],
      "enabled": true
    }
  }
}
```

### Environment Variables

The configuration supports environment variable substitution using `${VARIABLE_NAME}` syntax.

Add to your `.env` file:

```env
# Splunk MCP Server
SPLUNK_MCP_TOKEN=your-splunk-bearer-token-here
```

## How It Works

### 1. **Server Process Management**

When enabled, the `MCPServerManager`:
1. Spawns `npx mcp-remote` processes for each enabled server
2. Establishes JSON-RPC communication via stdin/stdout
3. Sends MCP protocol initialization messages
4. Lists available tools from each server
5. Converts MCP tools to LangChain tools

### 2. **Tool Conversion**

Each MCP tool is converted to a LangChain `StructuredTool`:
- Tool name: `{server_name}_{tool_name}` (e.g., `splunk-mcp_run_query`)
- Tool execution: Sends JSON-RPC `tools/call` request to MCP server
- Response handling: Extracts text content from MCP response

### 3. **Protocol Flow**

```
Application → MCP Server Process
            ↓
        1. initialize request
            ↓
        2. initialized notification  
            ↓
        3. tools/list request
            ↓
        4. tools/call requests (during execution)
```

## Enabling MCP Servers

### Step 1: Configure Servers

1. Edit `config/mcp_servers.json`
2. Set `"enabled": true` for servers you want to use
3. Ensure all required environment variables are set in `.env`

### Step 2: Update Environment Variables

Add your MCP server tokens to `.env`:

```env
SPLUNK_MCP_TOKEN=eyJraWQiOiJzcGx1bmsuc2VjcmV0IiwiYWxnIjoiSFM1MTIi...
```

### Step 3: Enable in Code

In `backend/main.py`, uncomment the MCP initialization block (around line 67-83):

```python
# Load MCP configuration
config_path = Path("config/mcp_servers.json")
if config_path.exists():
    logger.info(f"Loading MCP configuration from {config_path}")
    mcp_config = load_mcp_config(config_path)
    mcp_manager = MCPServerManager(mcp_config)
    await mcp_manager.initialize()
else:
    logger.warning(
        f"MCP configuration file not found: {config_path}. "
        "Agent will run without MCP tools."
    )
    mcp_manager = None
```

### Step 4: Install Node.js (if not already installed)

The MCP servers use `npx`, which requires Node.js:

```bash
# Check if Node.js is installed
node --version

# If not installed, install via homebrew (macOS)
brew install node

# Or download from https://nodejs.org
```

### Step 5: Restart Backend

```bash
./run_backend.sh
```

Check logs for:
```
INFO - Connecting to MCP server: splunk-mcp
INFO - Loaded 5 tool(s) from MCP server 'splunk-mcp'
```

## Available Tools

Once connected, tools will be available in the agent with names like:

- `splunk-mcp_run_splunk_query` - Execute SPL queries
- `splunk-mcp_get_indexes` - List Splunk indexes
- `splunk-mcp_get_metadata` - Get Splunk metadata
- `atlassian_search_jira` - Search Jira issues
- etc.

## Troubleshooting

### Issue: "command not found: npx"

**Solution**: Install Node.js
```bash
brew install node  # macOS
# or download from https://nodejs.org
```

### Issue: MCP server process fails to start

**Solution**: Check the logs for stderr output from the MCP process. Common issues:
- Invalid bearer token
- Network connectivity issues
- MCP server endpoint unavailable

### Issue: "Error listing tools"

**Solution**: 
- Verify the MCP server URL is correct
- Check authentication tokens are valid
- Ensure the MCP server supports the protocol version (2024-11-05)

### Issue: Tool calls fail

**Solution**:
- Check tool arguments match the expected schema
- Review MCP server logs (if available)
- Verify network connectivity to the remote server

## Testing MCP Connection Manually

You can test MCP servers directly:

```bash
# Test Splunk MCP server
npx -y mcp-remote \
  "https://cloud-architects.api.scs.splunk.com/cloud-architects/mcp/v1/" \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer YOUR_TOKEN"

# Send initialize request
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | npx -y mcp-remote ...
```

## Adding New MCP Servers

To add a new MCP server:

1. Add configuration to `config/mcp_servers.json`:
```json
{
  "mcpServers": {
    "my-new-server": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://my-server.example.com/mcp/v1/"
      ],
      "enabled": true
    }
  }
}
```

2. Add any required environment variables to `.env`

3. Restart the backend

## MCP Protocol Resources

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [mcp-remote Tool](https://github.com/modelcontextprotocol/mcp-remote)

## Human-in-the-Loop with MCP Tools

Sensitive MCP tools (like Splunk queries) can require human approval by adding them to the `SENSITIVE_TOOLS` set in `backend/agent/graph.py`:

```python
SENSITIVE_TOOLS = {
    "splunk-mcp_run_splunk_query",  # Requires approval
    "splunk-mcp_execute_sql",       # Requires approval
}
```

When these tools are called, the agent will pause and wait for user approval via the Streamlit UI.
