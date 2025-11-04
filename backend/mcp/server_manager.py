"""MCP server connection manager for remote MCP servers."""

import asyncio
import json
import logging
import os
from typing import Any, Type

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

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
        self._loop: asyncio.AbstractEventLoop | None = None

    async def initialize(self) -> None:
        """
        Initialize connections to all enabled MCP servers.

        This method should be called once during application startup.
        """
        if self._initialized:
            logger.warning("MCP server manager already initialized")
            return

        logger.info("Initializing MCP server connections...")
        
        # Store the event loop that creates the subprocesses
        self._loop = asyncio.get_running_loop()

        for server_name, server_config in self.enabled_servers.items():
            try:
                await self._connect_server(server_name, server_config)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{server_name}': {e}")

        self._initialized = True
        logger.info(
            f"MCP server initialization complete. Connected to {len(self.tools)} server(s)."
        )

    async def _connect_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        """
        Connect to a specific MCP server by spawning its process.

        Args:
            server_name: Name of the MCP server
            server_config: Configuration for the server
        """
        logger.info(f"Connecting to MCP server: {server_name}")
        logger.debug(f"Command: {server_config.command} {' '.join(server_config.args)}")

        try:
            # Spawn the MCP server process
            process = await asyncio.create_subprocess_exec(
                server_config.command,
                *server_config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **server_config.env} if server_config.env else None,
            )

            self.processes[server_name] = process
            
            # Start stderr reader task
            asyncio.create_task(self._log_stderr(server_name, process))

            # Initialize MCP connection and list tools
            tools = await self._initialize_mcp_connection(server_name, process)
            self.tools[server_name] = tools

            logger.info(f"Loaded {len(tools)} tool(s) from MCP server '{server_name}'")

        except Exception as e:
            logger.error(f"Error connecting to {server_name}: {e}", exc_info=True)
            raise
    
    async def _log_stderr(self, server_name: str, process: asyncio.subprocess.Process) -> None:
        """Log stderr output from MCP server process."""
        if process.stderr:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.warning(f"[{server_name} stderr] {line.decode().strip()}")

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
            logger.info(f"Sending initialize request to {server_name}...")
            
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
            init_response = await asyncio.wait_for(
                self._read_jsonrpc(process), timeout=10.0
            )
            
            logger.debug(f"Init response from {server_name}: {init_response}")

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

            logger.info(f"Requesting tools list from {server_name}...")
            
            # List available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }

            await self._send_jsonrpc(process, list_tools_request)
            tools_response = await asyncio.wait_for(
                self._read_jsonrpc(process), timeout=10.0
            )
            
            logger.debug(f"Tools response from {server_name}: {tools_response}")

            if "error" in tools_response:
                logger.error(f"Error listing tools for {server_name}: {tools_response['error']}")
                return tools

            # Convert MCP tools to LangChain tools
            mcp_tools = tools_response.get("result", {}).get("tools", [])
            for mcp_tool in mcp_tools:
                langchain_tool = self._convert_mcp_tool(server_name, mcp_tool, process)
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
        
        logger.debug(f"Converting tool {tool_name} with schema: {input_schema}")

        def tool_func(**kwargs: Any) -> str:
            """Execute the MCP tool."""
            logger.info(f"🔧 Executing MCP tool: {server_name}_{tool_name}")
            logger.debug(f"Tool arguments: {kwargs}")
            
            try:
                # Use the manager's event loop to execute the async call
                # This ensures we use the same loop where the subprocess was created
                result = self._execute_tool_sync(server_name, tool_name, kwargs, process)
                logger.info(f"✅ MCP tool {server_name}_{tool_name} completed successfully")
                return result

            except Exception as e:
                error_msg = f"❌ Error executing {tool_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return error_msg

        # Convert JSON schema to Pydantic model if available
        args_model = None
        if input_schema and "properties" in input_schema:
            args_model = self._create_pydantic_model(tool_name, input_schema)
        
        return StructuredTool.from_function(
            func=tool_func,  # Synchronous wrapper
            name=f"{server_name}_{tool_name}",
            description=tool_description,
            args_schema=args_model,  # Pydantic model for arguments
        )

    def _create_pydantic_model(self, tool_name: str, json_schema: dict[str, Any]) -> Type[BaseModel]:
        """
        Create a Pydantic model from a JSON schema.

        Args:
            tool_name: Name of the tool (for model naming)
            json_schema: JSON schema definition

        Returns:
            Pydantic model class
        """
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])
        
        # Build field definitions for Pydantic
        field_definitions = {}
        for prop_name, prop_schema in properties.items():
            prop_type = self._json_type_to_python(prop_schema)
            
            # Check if field is required
            if prop_name in required:
                # Required field
                default = ...  # Ellipsis means required in Pydantic
            else:
                # Optional field with None default
                default = None
                prop_type = prop_type | None  # type: ignore[assignment]
            
            # Add description if available
            description = prop_schema.get("description", "")
            
            field_definitions[prop_name] = (prop_type, default)
        
        # Create the model
        model_name = f"{tool_name.replace('-', '_').title()}Args"
        return create_model(model_name, **field_definitions)  # type: ignore[call-overload]
    
    def _json_type_to_python(self, schema: dict[str, Any]) -> type:
        """
        Convert JSON schema type to Python type.

        Args:
            schema: JSON schema for a property

        Returns:
            Python type
        """
        json_type = schema.get("type", "string")
        
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        return type_mapping.get(json_type, str)

    def _execute_tool_sync(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], process: asyncio.subprocess.Process
    ) -> str:
        """
        Execute MCP tool synchronously by scheduling on the correct event loop.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool
            arguments: Tool arguments
            process: MCP server process

        Returns:
            Tool result as string
        """
        if not self._loop:
            raise RuntimeError("MCP manager not properly initialized - no event loop stored")
        
        # Schedule the coroutine on the stored event loop
        future = asyncio.run_coroutine_threadsafe(
            self._execute_mcp_tool(server_name, tool_name, arguments, process),
            self._loop
        )
        
        # Wait for result with timeout
        try:
            result = future.result(timeout=30)
            return result
        except TimeoutError:
            return f"⏱️ MCP tool call timed out after 30s"
        except Exception as e:
            logger.error(f"Error in _execute_tool_sync: {e}", exc_info=True)
            return f"Error: {str(e)}"

    async def _execute_mcp_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], process: asyncio.subprocess.Process
    ) -> str:
        """
        Execute an MCP tool call.

        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            process: MCP server process

        Returns:
            Tool result as string
        """
        request_id = f"{server_name}_{tool_name}_{id(arguments)}"
        
        try:
            # Send tool call request
            call_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }

            logger.info(f"📤 Sending MCP request to {server_name}: {tool_name}")
            logger.debug(f"Request: {json.dumps(call_request, indent=2)}")
            
            await self._send_jsonrpc(process, call_request)
            
            # Read response with timeout
            logger.debug(f"⏳ Waiting for response from {server_name}...")
            response = await asyncio.wait_for(
                self._read_jsonrpc(process),
                timeout=25.0
            )
            
            logger.info(f"📥 Received response from {server_name}")
            logger.debug(f"Response: {json.dumps(response, indent=2)}")

            # Check for JSON-RPC error
            if "error" in response:
                error_detail = response["error"]
                error_msg = f"MCP Error from {server_name}: {error_detail.get('message', error_detail)}"
                logger.error(error_msg)
                return error_msg

            # Extract result
            result = response.get("result", {})
            
            # MCP tools return content in various formats
            # Try to extract the most useful representation
            if "content" in result:
                content = result["content"]
                
                # Content is typically a list of content items
                if isinstance(content, list) and len(content) > 0:
                    # Each item can be text, image, resource, etc.
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            else:
                                # For non-text content, include the type
                                text_parts.append(f"[{item.get('type', 'unknown')}]: {item}")
                        else:
                            text_parts.append(str(item))
                    
                    if text_parts:
                        return "\n".join(text_parts)
                
                # Fallback: return content as string
                return str(content)
            
            # No content field, return the whole result
            return json.dumps(result, indent=2)

        except asyncio.TimeoutError:
            error_msg = f"⏱️ MCP tool call timed out after 25s: {server_name}_{tool_name}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Error executing MCP tool {server_name}_{tool_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    async def _send_jsonrpc(
        self, process: asyncio.subprocess.Process, message: dict[str, Any]
    ) -> None:
        """Send a JSON-RPC message to the MCP server."""
        if not process.stdin:
            raise RuntimeError("Process stdin not available")
        
        message_str = json.dumps(message) + "\n"
        process.stdin.write(message_str.encode())
        await process.stdin.drain()
        logger.debug(f"📤 Sent: {message.get('method', message.get('id'))}")

    async def _read_jsonrpc(self, process: asyncio.subprocess.Process) -> dict[str, Any]:
        """Read a JSON-RPC response from the MCP server."""
        if not process.stdout:
            raise RuntimeError("Process stdout not available")
        
        line = await process.stdout.readline()
        if not line:
            raise RuntimeError("Received empty response from MCP server")
        
        try:
            response = json.loads(line.decode())
            logger.debug(f"📥 Received: {response.get('id', response.get('method', 'notification'))}")
            return response
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON-RPC response: {line.decode()}")
            raise RuntimeError(f"Invalid JSON-RPC response: {e}")

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
