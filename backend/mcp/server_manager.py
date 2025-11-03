"""MCP server connection manager for remote MCP servers."""

import asyncio
import json
import logging
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from backend.mcp.config import MCPConfig, MCPServerConfig, get_enabled_servers

logger = logging.getLogger(__name__)


class MCPServerManager:
    """
    Manager for MCP server connections and tool registration.

    This class handles:
    - Loading MCP server configurations
    - Spawning and managing MCP server processes (npx mcp-remote)
    - Converting MCP tools to LangChain tools
    - Managing tool lifecycle
    """

    def __init__(self, config: MCPConfig) -> None:
        """
        Initialize MCP server manager.

        Args:
            config: MCP configuration object
        """
        self.config = config
        self.enabled_servers = get_enabled_servers(config)
        self.tools: dict[str, list[BaseTool]] = {}
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize connections to all enabled MCP servers.

        This method should be called once during application startup.
        """
        if self._initialized:
            logger.warning("MCP server manager already initialized")
            return

        logger.info("Initializing MCP server connections...")

        for server_name, server_config in self.enabled_servers.items():
            try:
                await self._connect_server(server_name, server_config)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{server_name}': {e}")

        self._initialized = True
        logger.info(
            f"MCP server initialization complete. "
            f"Connected to {len(self.tools)} server(s)."
        )

    async def _connect_server(
        self, server_name: str, server_config: MCPServerConfig
    ) -> None:
        """
        Connect to a specific MCP server by spawning its process.

        Args:
            server_name: Name of the MCP server
            server_config: Configuration for the server
        """
        logger.info(f"Connecting to MCP server: {server_name}")

        try:
            # Spawn the MCP server process
            process = await asyncio.create_subprocess_exec(
                server_config.command,
                *server_config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**server_config.env} if server_config.env else None,
            )

            self.processes[server_name] = process

            # Initialize MCP connection and list tools
            tools = await self._initialize_mcp_connection(server_name, process)
            self.tools[server_name] = tools

            logger.info(
                f"Loaded {len(tools)} tool(s) from MCP server '{server_name}'"
            )

        except Exception as e:
            logger.error(f"Error connecting to {server_name}: {e}")
            raise

    async def _initialize_mcp_connection(
        self, server_name: str, process: asyncio.subprocess.Process
    ) -> list[BaseTool]:
        """
        Initialize MCP connection and retrieve available tools.

        Args:
            server_name: Name of the server
            process: The subprocess running the MCP server

        Returns:
            List of LangChain tools
        """
        tools: list[BaseTool] = []

        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "cursor-streamlit-mcp",
                        "version": "0.1.0",
                    },
                },
            }

            await self._send_jsonrpc(process, init_request)
            init_response = await self._read_jsonrpc(process)

            if "error" in init_response:
                logger.error(
                    f"MCP initialization error for {server_name}: {init_response['error']}"
                )
                return tools

            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            await self._send_jsonrpc(process, initialized_notification)

            # List available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }

            await self._send_jsonrpc(process, list_tools_request)
            tools_response = await self._read_jsonrpc(process)

            if "error" in tools_response:
                logger.error(
                    f"Error listing tools for {server_name}: {tools_response['error']}"
                )
                return tools

            # Convert MCP tools to LangChain tools
            mcp_tools = tools_response.get("result", {}).get("tools", [])
            for mcp_tool in mcp_tools:
                langchain_tool = self._convert_mcp_tool(
                    server_name, mcp_tool, process
                )
                tools.append(langchain_tool)

        except Exception as e:
            logger.error(f"Error initializing MCP connection for {server_name}: {e}")

        return tools

    def _convert_mcp_tool(
        self, server_name: str, mcp_tool: dict[str, Any], process: asyncio.subprocess.Process
    ) -> BaseTool:
        """
        Convert an MCP tool definition to a LangChain tool.

        Args:
            server_name: Name of the MCP server
            mcp_tool: MCP tool definition
            process: The MCP server process

        Returns:
            LangChain StructuredTool
        """
        tool_name = mcp_tool["name"]
        tool_description = mcp_tool.get("description", f"Tool: {tool_name}")
        input_schema = mcp_tool.get("inputSchema", {})

        async def tool_func(**kwargs: Any) -> str:
            """Execute the MCP tool."""
            try:
                # Send tool call request
                call_request = {
                    "jsonrpc": "2.0",
                    "id": asyncio.current_task().get_name() if asyncio.current_task() else "tool-call",  # type: ignore[union-attr]
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": kwargs},
                }

                await self._send_jsonrpc(process, call_request)
                response = await self._read_jsonrpc(process)

                if "error" in response:
                    return f"Error calling {tool_name}: {response['error']}"

                result = response.get("result", {})
                content = result.get("content", [])

                # Extract text content from MCP response
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", str(result))
                return str(result)

            except Exception as e:
                logger.error(f"Error executing MCP tool {tool_name}: {e}")
                return f"Error: {str(e)}"

        return StructuredTool.from_function(
            coroutine=tool_func,
            name=f"{server_name}_{tool_name}",
            description=tool_description,
        )

    async def _send_jsonrpc(
        self, process: asyncio.subprocess.Process, message: dict[str, Any]
    ) -> None:
        """Send a JSON-RPC message to the MCP server."""
        if process.stdin:
            message_str = json.dumps(message) + "\n"
            process.stdin.write(message_str.encode())
            await process.stdin.drain()

    async def _read_jsonrpc(self, process: asyncio.subprocess.Process) -> dict[str, Any]:
        """Read a JSON-RPC response from the MCP server."""
        if process.stdout:
            line = await process.stdout.readline()
            return json.loads(line.decode())
        return {"error": "No stdout available"}

    def get_all_tools(self) -> list[BaseTool]:
        """
        Get all tools from all connected MCP servers.

        Returns:
            Flat list of all available tools
        """
        if not self._initialized:
            logger.warning("MCP server manager not initialized. Call initialize() first.")
            return []

        all_tools = []
        for server_tools in self.tools.values():
            all_tools.extend(server_tools)

        return all_tools

    def get_tools_by_server(self, server_name: str) -> list[BaseTool]:
        """
        Get tools from a specific MCP server.

        Args:
            server_name: Name of the MCP server

        Returns:
            List of tools from that server
        """
        return self.tools.get(server_name, [])

    async def shutdown(self) -> None:
        """Shutdown all MCP server connections."""
        logger.info("Shutting down MCP server connections...")

        for server_name, process in self.processes.items():
            try:
                process.terminate()
                await process.wait()
                logger.info(f"Terminated MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Error terminating {server_name}: {e}")

        self._initialized = False
        self.tools.clear()
        self.processes.clear()

        logger.info("MCP server connections closed")
