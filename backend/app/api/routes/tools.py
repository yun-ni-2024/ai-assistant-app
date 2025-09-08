"""
MCP tools management API routes.

This module provides API endpoints for managing and executing MCP tools.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from ...services.tools import get_tool_registry


router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfo(BaseModel):
    """Information about an MCP tool."""
    name: str
    description: str
    enabled: bool


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
        tool_registry = get_tool_registry()
        available_tools = tool_registry.get_available_tools()
        
        return [
            ToolInfo(
                name=tool_name,
                description=config.get("description", ""),
                enabled=config.get("enabled", True)
            )
            for tool_name, config in available_tools.items()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.get("/enabled", response_model=List[ToolInfo])
async def list_enabled_tools() -> List[ToolInfo]:
    """List only enabled MCP tools."""
    try:
        tool_registry = get_tool_registry()
        available_tools = tool_registry.get_available_tools()
        
        return [
            ToolInfo(
                name=tool_name,
                description=config.get("description", ""),
                enabled=config.get("enabled", True)
            )
            for tool_name, config in available_tools.items()
            if config.get("enabled", True)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list enabled tools: {str(e)}")


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(request: ToolExecutionRequest = Body(...)) -> ToolExecutionResponse:
    """Execute an MCP tool with given parameters."""
    try:
        tool_registry = get_tool_registry()
        
        # Validate tool exists and is enabled
        if not tool_registry.is_tool_enabled(request.tool_name):
            raise HTTPException(
                status_code=400, 
                detail=f"Tool '{request.tool_name}' is not available or not enabled"
            )
        
        # Create tool instance
        tool_instance = tool_registry.create_tool_instance(request.tool_name)
        if not tool_instance:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create tool instance for '{request.tool_name}'"
            )
        
        # Execute the tool
        result = await tool_instance.execute(request.parameters)
        
        return ToolExecutionResponse(
            tool_name=request.tool_name,
            result=result,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.get("/{tool_name}/info", response_model=ToolInfo)
async def get_tool_info(tool_name: str) -> ToolInfo:
    """Get information about a specific tool."""
    try:
        tool_registry = get_tool_registry()
        tool_config = tool_registry.get_tool_config(tool_name)
        
        if not tool_config:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        return ToolInfo(
            name=tool_name,
            description=tool_config.get("description", ""),
            enabled=tool_config.get("enabled", True)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tool info: {str(e)}")


@router.get("/health")
async def tools_health_check() -> Dict[str, Any]:
    """Health check for MCP tools service."""
    try:
        tool_registry = get_tool_registry()
        available_tools = tool_registry.get_available_tools()
        enabled_tools = [name for name, config in available_tools.items() if config.get("enabled", True)]
        
        # Check environment variables
        import os
        google_api_key = os.getenv("GOOGLE_CSE_API_KEY", "")
        google_engine_id = os.getenv("GOOGLE_CSE_ENGINE_ID", "")
        
        return {
            "status": "healthy",
            "total_tools": len(available_tools),
            "enabled_tools": len(enabled_tools),
            "tools": enabled_tools,
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
