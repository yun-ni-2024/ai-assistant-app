"""
Fetch tool for web content retrieval and analysis.
Provides webpage content extraction using httpx and BeautifulSoup4.
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, Any, List
from datetime import datetime


class FetchTool:
    """Web content fetching tool using httpx and BeautifulSoup4."""
    
    def __init__(self):
        """Initialize the fetch tool."""
        self.timeout = 30.0
        self.max_content_length = 8000
    
    def get_tool_description(self) -> str:
        """Return a description of what this tool does."""
        return "Web content fetching tool that retrieves and analyzes specific webpage content. Can extract text, titles, links, and other information from any accessible webpage."
    
    def get_usage_conditions(self) -> str:
        """Return the conditions under which this tool should be used."""
        return """Use this tool when:
1. User provides a specific URL (http:// or https://) in their message
2. User mentions "this webpage", "this link", "analyze this page"
3. User asks to analyze, read, or get content from a specific webpage
4. User refers to a previously mentioned URL in the conversation
5. User wants to extract information from a specific webpage
6. User asks "what does this page say", "analyze this link", etc.
7. User provides a URL and asks questions about its content"""
    
    def get_tool_selection_prompt(self) -> str:
        """Return the prompt for tool selection analysis."""
        return f"""Tool: fetch
Description: {self.get_tool_description()}
Usage Conditions: {self.get_usage_conditions()}

This tool should be selected when the user provides a specific URL or wants to analyze content from a specific webpage."""
    
    def get_parameter_extraction_prompt(self) -> str:
        """Return the prompt template for extracting fetch parameters from user messages."""
        return """Extract fetch parameters from the user message and conversation context.

User Message: {user_message}
Conversation Context: {conversation_context}

Instructions:
1. Look for URLs (http:// or https://) in the user's message
2. If user mentions "this webpage", "this link", "analyze this page", look for URLs in conversation context
3. If user provides a URL directly, use that URL
4. If user refers to a previously mentioned URL, extract it from conversation context
5. Ensure the URL is valid and complete

Please respond in this exact JSON format:
{{
    "url": "extracted or referenced URL"
}}

Examples:
- "Analyze this webpage: https://example.com" → {{"url": "https://example.com"}}
- "This link: https://news.com" → {{"url": "https://news.com"}}
- "What does this page say about AI?" (after URL was mentioned) → {{"url": "previously_mentioned_url"}}
- "What does this webpage contain?" (after URL was mentioned) → {{"url": "previously_mentioned_url"}}"""
    
    def get_system_message_template(self) -> str:
        """Return the system message template for formatting fetch results."""
        return """I have retrieved webpage content for you. Here is the information:

{tool_result}

Please answer the user's question based on this webpage content: {user_message}

IMPORTANT: This webpage content contains REAL information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the webpage content clearly contains relevant information.

Guidelines for webpage content analysis:
1. Extract and present ALL relevant information from the webpage content
2. Look for specific data, numbers, facts, and concrete information that directly relate to the user's question
3. Focus on analyzing and summarizing the content rather than citing sources
4. If the webpage content contains specific data, numbers, or facts, present them clearly and prominently
5. Provide a comprehensive analysis based on the webpage content
6. If there are related links in the content, you may mention them naturally but don't over-emphasize them
7. Adapt your response to match the user's language and cultural context

Please respond in the same language as the user's question and provide a thorough analysis of the webpage content."""
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute web content fetching based on LLM-analyzed parameters.
        
        Args:
            parameters: Dictionary containing fetch parameters
                - url (str): URL to fetch and analyze
        
        Returns:
            Dictionary containing fetched content with the following structure:
            {
                "url": str,
                "title": str,
                "content": str,
                "summary": str,
                "links": List[Dict],
                "status_code": int,
                "content_type": str
            }
        """
        try:
            url = parameters.get("url", "")
            
            if not url:
                return {
                    "url": "",
                    "title": "No URL provided",
                    "content": "",
                    "summary": "",
                    "links": [],
                    "status_code": 0,
                    "content_type": "",
                    "error": "No URL provided"
                }
            
            if not self._is_valid_url(url):
                return {
                    "url": url,
                    "title": "Invalid URL",
                    "content": "",
                    "summary": "",
                    "links": [],
                    "status_code": 0,
                    "content_type": "",
                    "error": "Invalid URL format"
                }
            
            # Fetch the webpage content
            content_data = await self._fetch_webpage(url)
            
            if content_data.get("error"):
                return content_data
            
            # Parse the content
            parsed_data = self._parse_webpage_content(content_data["html"], url)
            
            return {
                "url": url,
                "title": parsed_data["title"],
                "content": parsed_data["content"],
                "summary": parsed_data["summary"],
                "links": parsed_data["links"],
                "status_code": content_data["status_code"],
                "content_type": content_data["content_type"]
            }
            
        except Exception as e:
            return {
                "url": parameters.get("url", ""),
                "title": "Error",
                "content": "",
                "summary": "",
                "links": [],
                "status_code": 0,
                "content_type": "",
                "error": f"Fetch tool error: {str(e)}"
            }
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if the URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    async def _fetch_webpage(self, url: str) -> Dict[str, Any]:
        """Fetch webpage content using httpx."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                
                return {
                    "html": response.text,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "error": None
                }
                
        except httpx.TimeoutException:
            return {
                "html": "",
                "status_code": 0,
                "content_type": "",
                "error": "Request timeout"
            }
        except httpx.HTTPStatusError as e:
            return {
                "html": "",
                "status_code": e.response.status_code,
                "content_type": "",
                "error": f"HTTP error: {e.response.status_code}"
            }
        except Exception as e:
            return {
                "html": "",
                "status_code": 0,
                "content_type": "",
                "error": f"Request error: {str(e)}"
            }
    
    def _parse_webpage_content(self, html: str, base_url: str) -> Dict[str, Any]:
        """Parse HTML content and extract relevant information."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract title
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Extract main content
            content = ""
            
            # Try to find main content areas
            main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
            if main_content:
                content = main_content.get_text(separator=" ", strip=True)
            else:
                # Fallback to body content
                body = soup.find("body")
                if body:
                    content = body.get_text(separator=" ", strip=True)
            
            # Clean up content
            content = " ".join(content.split())
            
            # Limit content length
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "..."
            
            # Generate summary (first 200 characters)
            summary = content[:200] + "..." if len(content) > 200 else content
            
            # Extract links
            links = []
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                text = link.get_text().strip()
                
                if href and text:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(base_url, href)
                    links.append({
                        "text": text,
                        "url": absolute_url
                    })
            
            # Limit number of links
            links = links[:10]
            
            return {
                "title": title,
                "content": content,
                "summary": summary,
                "links": links
            }
            
        except Exception as e:
            return {
                "title": "Parse Error",
                "content": "",
                "summary": "",
                "links": [],
                "error": f"Content parsing error: {str(e)}"
            }


# Factory function for tool creation
def create_fetch_tool(config: Dict[str, Any] = None) -> FetchTool:
    """Create and return a new FetchTool instance."""
    # FetchTool doesn't use config, so we ignore it
    return FetchTool()
