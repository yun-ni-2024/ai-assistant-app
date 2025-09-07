"""
MCP (Model Context Protocol) client service.

This module provides a client for communicating with MCP servers
and executing tools to extend AI capabilities.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import httpx
from ..core.mcp_config import get_enabled_tools, get_tool_config, is_tool_enabled
from ..db.database import db_connection


class MCPToolError(Exception):
    """Exception raised when MCP tool execution fails."""
    pass


class MCPClient:
    """Client for communicating with MCP servers and executing tools."""
    
    def __init__(self):
        self.tools = get_enabled_tools()
        self._http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()
    
    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "enabled": tool.enabled,
                "server_url": tool.server_url
            }
            for tool in self.tools.values()
        ]
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        session_id: str,
        message_id: str
    ) -> Dict[str, Any]:
        """Execute a specific MCP tool with given parameters."""
        
        if not is_tool_enabled(tool_name):
            raise MCPToolError(f"Tool '{tool_name}' is not enabled")
        
        tool_config = get_tool_config(tool_name)
        tool_call_id = str(uuid.uuid4())
        
        try:
            # Record tool call start
            await self._record_tool_call(
                tool_call_id, session_id, message_id, 
                tool_name, parameters, "running"
            )
            
            # Execute the tool based on its type
            if tool_name == "search":
                result = await self._execute_search_tool(parameters, tool_config)
            elif tool_name == "fetch":
                result = await self._execute_fetch_tool(parameters, tool_config)
            elif tool_name == "memory":
                result = await self._execute_memory_tool(parameters, tool_config)
            else:
                raise MCPToolError(f"Unknown tool type: {tool_name}")
            
            # Record successful tool call
            await self._update_tool_call(
                tool_call_id, result, "success"
            )
            
            return {
                "tool_name": tool_name,
                "result": result,
                "status": "success"
            }
            
        except Exception as e:
            # Record failed tool call
            error_result = {"error": str(e)}
            await self._update_tool_call(
                tool_call_id, error_result, "error"
            )
            raise MCPToolError(f"Tool execution failed: {str(e)}")
    
    async def _execute_search_tool(
        self, 
        parameters: Dict[str, Any], 
        tool_config
    ) -> Dict[str, Any]:
        """Execute search tool using Google Custom Search API."""
        query = parameters.get("query", "")
        api_key = tool_config.api_key
        engine_id = tool_config.engine_id
        
        if not api_key or not engine_id:
            raise MCPToolError("Google Custom Search API not configured")
        
        try:
            # Call Google Custom Search API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": api_key,
                        "cx": engine_id,
                        "q": query,
                        "num": 10,
                        # "lr": "lang_zh-CN",  # Removed language restriction for better multilingual support
                        "safe": "medium",
                        "sort": "date",  # Sort by date for latest results
                        "fields": "items(title,link,snippet,pagemap),searchInformation(totalResults,searchTime)"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MCPToolError(f"Search API error: {error_msg}")
                
                data = response.json()
                return self._format_google_search_results(data, query)
                
        except httpx.TimeoutException:
            raise MCPToolError("Search request timed out")
        except httpx.RequestError as e:
            raise MCPToolError(f"Search request failed: {str(e)}")
        except Exception as e:
            raise MCPToolError(f"Search execution failed: {str(e)}")
    
    def _format_google_search_results(self, api_data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format Google Custom Search API results."""
        results = []
        
        for item in api_data.get("items", []):
            # Extract published date if available
            published_date = ""
            if "pagemap" in item and "metatags" in item["pagemap"]:
                metatags = item["pagemap"]["metatags"]
                if metatags and len(metatags) > 0:
                    published_date = metatags[0].get("article:published_time", "")
            
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": self._extract_domain(item.get("link", "")),
                "published_date": published_date
            })
        
        search_info = api_data.get("searchInformation", {})
        
        return {
            "query": query,
            "results": results,
            "total_results": search_info.get("totalResults", "0"),
            "search_time": float(search_info.get("searchTime", 0)),
            "api_source": "google_custom_search"
        }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return url
    
    async def _execute_fetch_tool(
        self, 
        parameters: Dict[str, Any], 
        tool_config
    ) -> Dict[str, Any]:
        """Execute fetch tool to retrieve and parse webpage content."""
        url = parameters.get("url", "")
        
        if not url:
            raise MCPToolError("URL parameter is required for fetch tool")
        
        # Validate URL format
        if not self._is_valid_url(url):
            raise MCPToolError(f"Invalid URL format: {url}")
        
        try:
            # Fetch webpage content
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    },
                    follow_redirects=True
                )
                
                if response.status_code != 200:
                    raise MCPToolError(f"HTTP {response.status_code}: Failed to fetch URL")
                
                # Parse content
                content_info = self._parse_webpage_content(response.text, url)
                
                return {
                    "url": url,
                    "title": content_info["title"],
                    "content": content_info["content"],
                    "summary": content_info["summary"],
                    "links": content_info["links"],
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "content_length": len(response.text),
                    "fetch_time": content_info["fetch_time"]
                }
                
        except httpx.TimeoutException:
            raise MCPToolError(f"Request timeout while fetching {url}")
        except httpx.RequestError as e:
            raise MCPToolError(f"Request failed: {str(e)}")
        except Exception as e:
            raise MCPToolError(f"Fetch execution failed: {str(e)}")
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _parse_webpage_content(self, html_content: str, url: str) -> Dict[str, Any]:
        """Parse webpage content and extract useful information."""
        from datetime import datetime
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()
            
            # Extract main content
            content = ""
            
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|article|post'))
            
            if main_content:
                content = main_content.get_text(separator=' ', strip=True)
            else:
                # Fallback to body content
                body = soup.find('body')
                if body:
                    content = body.get_text(separator=' ', strip=True)
                else:
                    content = soup.get_text(separator=' ', strip=True)
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content)  # Replace multiple whitespace with single space
            content = content.strip()
            
            # Limit content length to avoid token limits
            max_content_length = 8000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip()
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                elif not href.startswith(('http://', 'https://')):
                    continue
                
                if text and len(text) < 100:  # Only include links with reasonable text
                    links.append({
                        "url": href,
                        "text": text
                    })
            
            # Limit number of links
            links = links[:20]
            
            # Generate summary (first 500 characters)
            summary = content[:500] + "..." if len(content) > 500 else content
            
            return {
                "title": title,
                "content": content,
                "summary": summary,
                "links": links,
                "fetch_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            # Fallback to basic text extraction
            import re
            content = re.sub(r'<[^>]+>', '', html_content)  # Remove HTML tags
            content = re.sub(r'\s+', ' ', content).strip()  # Clean whitespace
            
            return {
                "title": "Unknown",
                "content": content[:8000] if len(content) > 8000 else content,
                "summary": content[:500] + "..." if len(content) > 500 else content,
                "links": [],
                "fetch_time": datetime.now().isoformat()
            }
    
    async def _execute_memory_tool(
        self, 
        parameters: Dict[str, Any], 
        tool_config
    ) -> Dict[str, Any]:
        """Execute memory tool (simulated for now)."""
        action = parameters.get("action", "get")
        key = parameters.get("key", "")
        value = parameters.get("value", "")
        
        # For now, return a simulated memory result
        # In a real implementation, this would call the actual MCP server
        if action == "set":
            return {"status": "stored", "key": key, "value": value}
        elif action == "get":
            return {"status": "retrieved", "key": key, "value": f"记忆中的值: {key}"}
        else:
            return {"status": "unknown_action", "action": action}
    
    async def _record_tool_call(
        self,
        tool_call_id: str,
        session_id: str,
        message_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        status: str
    ):
        """Record a tool call in the database."""
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO tool_calls (id, session_id, message_id, tool_name, parameters, result, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_call_id,
                    session_id,
                    message_id,
                    tool_name,
                    json.dumps(parameters),
                    "",
                    status,
                    datetime.now(timezone.utc).isoformat()
                )
            )
    
    async def _update_tool_call(
        self,
        tool_call_id: str,
        result: Dict[str, Any],
        status: str
    ):
        """Update a tool call result in the database."""
        with db_connection() as conn:
            conn.execute(
                """
                UPDATE tool_calls 
                SET result = ?, status = ?
                WHERE id = ?
                """,
                (
                    json.dumps(result),
                    status,
                    tool_call_id
                )
            )


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def close_mcp_client():
    """Close the global MCP client."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
