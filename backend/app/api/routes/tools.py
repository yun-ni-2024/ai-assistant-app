"""
MCP tools management API routes.

This module provides API endpoints for managing and executing MCP tools.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from ...services.mcp_client import get_mcp_client, MCPToolError
from ...core.mcp_config import get_enabled_tools, is_tool_enabled


router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfo(BaseModel):
    """Information about an MCP tool."""
    name: str
    description: str
    enabled: bool
    server_url: str


class ToolExecutionRequest(BaseModel):
    """Request to execute an MCP tool."""
    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the tool")
    session_id: str = Field(..., description="Session ID for tracking")
    message_id: str = Field(..., description="Message ID for tracking")


class ToolExecutionResponse(BaseModel):
    """Response from tool execution."""
    tool_name: str
    result: Dict[str, Any]
    status: str


@router.get("/", response_model=List[ToolInfo])
async def list_tools() -> List[ToolInfo]:
    """List all available MCP tools."""
    try:
        mcp_client = get_mcp_client()
        tools = await mcp_client.list_available_tools()
        
        return [
            ToolInfo(
                name=tool["name"],
                description=tool["description"],
                enabled=tool["enabled"],
                server_url=tool["server_url"]
            )
            for tool in tools
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.get("/enabled", response_model=List[ToolInfo])
async def list_enabled_tools() -> List[ToolInfo]:
    """List only enabled MCP tools."""
    try:
        enabled_tools = get_enabled_tools()
        
        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                enabled=tool.enabled,
                server_url=tool.server_url
            )
            for tool in enabled_tools.values()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list enabled tools: {str(e)}")


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(request: ToolExecutionRequest = Body(...)) -> ToolExecutionResponse:
    """Execute an MCP tool with given parameters."""
    try:
        # Validate tool exists and is enabled
        if not is_tool_enabled(request.tool_name):
            raise HTTPException(
                status_code=400, 
                detail=f"Tool '{request.tool_name}' is not available or not enabled"
            )
        
        mcp_client = get_mcp_client()
        result = await mcp_client.execute_tool(
            tool_name=request.tool_name,
            parameters=request.parameters,
            session_id=request.session_id,
            message_id=request.message_id
        )
        
        return ToolExecutionResponse(
            tool_name=result["tool_name"],
            result=result["result"],
            status=result["status"]
        )
        
    except MCPToolError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.get("/{tool_name}/info", response_model=ToolInfo)
async def get_tool_info(tool_name: str) -> ToolInfo:
    """Get information about a specific tool."""
    try:
        mcp_client = get_mcp_client()
        tools = await mcp_client.list_available_tools()
        
        tool_info = next((tool for tool in tools if tool["name"] == tool_name), None)
        if not tool_info:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        return ToolInfo(
            name=tool_info["name"],
            description=tool_info["description"],
            enabled=tool_info["enabled"],
            server_url=tool_info["server_url"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tool info: {str(e)}")


@router.get("/health")
async def tools_health_check() -> Dict[str, Any]:
    """Health check for MCP tools service."""
    try:
        mcp_client = get_mcp_client()
        tools = await mcp_client.list_available_tools()
        enabled_tools = [tool for tool in tools if tool["enabled"]]
        
        # Check environment variables
        import os
        google_api_key = os.getenv("GOOGLE_CSE_API_KEY", "")
        google_engine_id = os.getenv("GOOGLE_CSE_ENGINE_ID", "")
        
        return {
            "status": "healthy",
            "total_tools": len(tools),
            "enabled_tools": len(enabled_tools),
            "tools": [tool["name"] for tool in enabled_tools],
            "env_check": {
                "google_api_key_loaded": bool(google_api_key),
                "google_engine_id_loaded": bool(google_engine_id),
                "google_api_key_length": len(google_api_key) if google_api_key else 0,
                "google_engine_id_length": len(google_engine_id) if google_engine_id else 0
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
