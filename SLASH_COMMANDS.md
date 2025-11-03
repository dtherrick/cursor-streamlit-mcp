# Slash Commands Reference

## Overview

The chat interface supports special slash commands (similar to Claude CLI or Gemini CLI) that provide information about the system without invoking the AI agent.

## Available Commands

### `/mcp`
**List MCP servers and their tools**

Shows:
- Which MCP servers are enabled
- How many tools each server provides
- List of available tools from each server
- Total tool count across all servers

Example output:
```
**MCP Servers**
**Enabled Servers**: 2

**splunk-mcp**
  - Command: `npx`
  - Tools: 5
  - Available tools:
    • `splunk-mcp_run_splunk_query`: Execute SPL queries...
    • `splunk-mcp_get_indexes`: List Splunk indexes...
    • `splunk-mcp_get_metadata`: Get Splunk metadata...

**atlassian**
  - Command: `npx`
  - Tools: 3
  - Available tools:
    • `atlassian_search_jira`: Search Jira issues...

**Total Tools Available**: 8
```

### `/tools`
**List all available tools across all sources**

Shows all tools grouped by type:
- **MCP Tools**: Tools from MCP servers (Splunk, Atlassian, etc.)
- **RAG Tools**: Document retrieval and search tools
- **Other Tools**: Any additional tools

Example output:
```
**Available Tools**
**Total Tools**: 6

**MCP Tools** (5):
  • `splunk-mcp_run_splunk_query`
    Execute a Splunk SPL query. Use this to search and analyze Splunk data...

**RAG Tools** (1):
  • `retrieve_documents`
    Retrieve relevant documents from the knowledge base...
```

### `/help`
**Show available commands and usage examples**

Displays:
- List of all slash commands
- How to use the chat interface
- Example queries
- Information about MCP servers

## Usage

Simply type the command in the chat input:

```
/mcp
```

```
/tools
```

```
/help
```

## When to Use

### Use `/mcp` when you want to:
- See which MCP servers are connected
- Check if Splunk/Atlassian integration is working
- Verify what tools are available from each server
- Troubleshoot MCP connection issues

### Use `/tools` when you want to:
- See all available capabilities
- Understand what the agent can do
- Check if a specific tool is loaded
- Debug tool-related issues

### Use `/help` when you want to:
- Learn about available commands
- See usage examples
- Get started with the system

## Implementation Details

- Commands are processed server-side in `backend/api/routes.py`
- Commands bypass the AI agent for instant response
- Commands don't count against your AI usage/costs
- Command responses are formatted in Markdown
- Commands work even if the agent is having issues

## Adding New Commands

To add a new slash command:

1. Add the command handler in `backend/api/routes.py`:
```python
async def get_my_new_command(thread_id: str) -> ChatResponse:
    """Handle /mynewcommand"""
    return ChatResponse(
        response="Your command output here",
        thread_id=thread_id,
        requires_approval=False,
        approval_details=None,
    )
```

2. Register it in `handle_special_command()`:
```python
elif cmd == "/mynewcommand":
    return await get_my_new_command(thread_id)
```

3. Update the help text in `get_help_info()`

4. Update this documentation

## Future Enhancements

Potential additional commands:
- `/status` - System health and component status
- `/config` - Current configuration settings
- `/history` - Conversation history management
- `/clear` - Clear conversation state
- `/docs` - List indexed documents
- `/traces` - Recent LangSmith trace links

