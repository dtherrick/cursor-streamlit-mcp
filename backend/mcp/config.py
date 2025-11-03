"""MCP server configuration loader."""

import json
import os
from pathlib import Path
from string import Template

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str]
    enabled: bool = True
    env: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    """Root configuration for all MCP servers."""

    mcpServers: dict[str, MCPServerConfig]


def load_mcp_config(config_path: str | Path = "config/mcp_servers.json") -> MCPConfig:
    """
    Load MCP server configuration from JSON file.

    Args:
        config_path: Path to the MCP configuration JSON file

    Returns:
        MCPConfig object containing all server configurations

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"MCP configuration file not found: {config_path}")

    with open(config_path) as f:
        config_data = json.load(f)

    # Substitute environment variables in args
    for server_name, server_config in config_data.get("mcpServers", {}).items():
        if "args" in server_config:
            server_config["args"] = [
                Template(arg).safe_substitute(os.environ) for arg in server_config["args"]
            ]

    return MCPConfig(**config_data)


def get_enabled_servers(config: MCPConfig) -> dict[str, MCPServerConfig]:
    """
    Get only enabled MCP servers from configuration.

    Args:
        config: The MCP configuration object

    Returns:
        Dictionary of enabled server names to their configurations
    """
    return {
        name: server_config
        for name, server_config in config.mcpServers.items()
        if server_config.enabled
    }
