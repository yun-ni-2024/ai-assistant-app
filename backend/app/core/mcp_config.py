"""
MCP (Model Context Protocol) tool configuration.

This module defines the available MCP tools and their configurations.
Tools are designed to extend the AI's capabilities beyond its training data.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MCPToolConfig:
    """Configuration for a single MCP tool."""
    
    def __init__(
        self,
        name: str,
        description: str,
        enabled: bool = True,
        server_url: str = "",
        api_key: str = "",
        engine_id: str = "",
        search_engine: str = "",
        **kwargs
    ):
        self.name = name
        self.description = description
        self.enabled = enabled
        self.server_url = server_url
        self.api_key = api_key
        self.engine_id = engine_id
        self.search_engine = search_engine
        self.extra_config = kwargs


# MCP Tools Configuration
MCP_TOOLS: Dict[str, MCPToolConfig] = {
    "search": MCPToolConfig(
        name="search",
        description="网络搜索功能，可以搜索最新的信息和新闻",
        enabled=os.getenv("MCP_SEARCH_ENABLED", "true").lower() == "true",
        server_url=os.getenv("MCP_SEARCH_URL", "http://localhost:3001"),
        api_key=os.getenv("GOOGLE_CSE_API_KEY", ""),
        engine_id=os.getenv("GOOGLE_CSE_ENGINE_ID", ""),
        search_engine="google"
    ),
    
    "fetch": MCPToolConfig(
        name="fetch",
        description="网页内容获取功能，可以获取指定URL的内容",
        enabled=os.getenv("MCP_FETCH_ENABLED", "true").lower() == "true",
        server_url=os.getenv("MCP_FETCH_URL", "http://localhost:3002"),
    ),
    
    "memory": MCPToolConfig(
        name="memory",
        description="持久化记忆功能，可以存储和检索用户偏好",
        enabled=os.getenv("MCP_MEMORY_ENABLED", "true").lower() == "true",
        server_url=os.getenv("MCP_MEMORY_URL", "http://localhost:3003"),
    ),
}


def get_enabled_tools() -> Dict[str, MCPToolConfig]:
    """Get all enabled MCP tools."""
    return {name: config for name, config in MCP_TOOLS.items() if config.enabled}


def get_tool_config(tool_name: str) -> MCPToolConfig:
    """Get configuration for a specific tool."""
    if tool_name not in MCP_TOOLS:
        raise ValueError(f"Tool '{tool_name}' not found")
    return MCP_TOOLS[tool_name]


def is_tool_enabled(tool_name: str) -> bool:
    """Check if a tool is enabled."""
    if tool_name not in MCP_TOOLS:
        return False
    return MCP_TOOLS[tool_name].enabled
