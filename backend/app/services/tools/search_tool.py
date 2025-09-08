"""
Search tool for web search functionality.
Provides real-time information retrieval using Google Custom Search API.
"""

import asyncio
import httpx
from typing import Dict, Any, List


class SearchTool:
    """Web search tool using Google Custom Search API."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the search tool with API configuration."""
        self.config = config or {}
        self.api_key = self.config["api_key"]
        self.engine_id = self.config["engine_id"]
        self.base_url = self.config.get("base_url", "https://www.googleapis.com/customsearch/v1")
    
    def get_tool_description(self) -> str:
        """Return a description of what this tool does."""
        return "Web search tool that provides real-time information retrieval using Google Custom Search API. Can search for current events, news, weather, facts, and any information available on the web."
    
    def get_usage_conditions(self) -> str:
        """Return the conditions under which this tool should be used."""
        return """Use this tool when:
1. User asks for real-time information, current events, or latest data
2. User wants to know about recent news, weather, or current happenings
3. User asks questions that require up-to-date information not in general knowledge
4. User wants to search for specific topics, people, or events
5. User asks "what's happening", "latest news", "current status", etc.
6. User needs information that changes frequently (stock prices, weather, news)
7. User asks about recent developments or updates on any topic"""
    
    def get_tool_selection_prompt(self) -> str:
        """Return the prompt for tool selection analysis."""
        return f"""Tool: search
Description: {self.get_tool_description()}
Usage Conditions: {self.get_usage_conditions()}

This tool should be selected when the user's question requires real-time, current, or up-to-date information that is not available in general knowledge."""
    
    def get_parameter_extraction_prompt(self) -> str:
        """Return the prompt template for extracting search parameters from user messages."""
        return """Extract search parameters from the user message and conversation context.

User Message: {user_message}
Conversation Context: {conversation_context}

Instructions:
1. Analyze the user's message to understand what they want to search for
2. Consider the conversation context when interpreting pronouns like "it", "this", "that"
3. Generate search query in the SAME LANGUAGE as the user's message
4. If user asks about "latest", "recent", "today", "current" information, include those keywords
5. Make the search query specific and relevant to the user's question

Please respond in this exact JSON format:
{{
    "query": "extracted search query in user's language"
}}

Examples:
- "What's the weather like today?" → {{"query": "weather today"}}
- "What's the latest AI news?" → {{"query": "latest AI news"}}
- "Tell me about its recent developments" (after discussing AI) → {{"query": "AI recent developments"}}
- "What are the latest updates about this?" (after discussing AI) → {{"query": "AI latest updates"}}"""
    
    def get_system_message_template(self) -> str:
        """Return the system message template for formatting search results."""
        return """I have searched for relevant information for you. Here are the search results:

{tool_result}

Please answer the user's question based on these search results: {user_message}

IMPORTANT: These search results contain REAL-TIME, CURRENT information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the search results clearly contain relevant information.

Guidelines:
1. CAREFULLY FILTER search results - only include information that is DIRECTLY relevant to the user's specific question
2. IGNORE search results that are not related to the user's question, even if they appear in the search results
3. Focus on extracting specific data, numbers, facts, and concrete information that directly relate to the user's question
4. If multiple sources mention the same relevant information, present it as confirmed data
5. ACTIVELY embed URLs as inline references throughout your response using markdown link format: [descriptive text](URL)
6. When mentioning specific data, facts, or information, immediately follow with the source link in the same sentence
7. Make URLs an integral part of your response, not just an afterthought - weave them naturally into the text
8. If the search results contain specific data, numbers, or facts, present them clearly and prominently with their source links
9. Adapt all formatting, headings, and labels to match the user's language and cultural context

CONTENT FILTERING RULES:
- Only include information that is DIRECTLY relevant to the user's specific question
- IGNORE search results that are not related to the user's question, even if they appear in the search results
- Don't feel obligated to use all search results - quality and relevance are more important than quantity
- If search results are mostly irrelevant, acknowledge this and provide what relevant information you can find
- Examples: If user asks about finance but results include entertainment news, ignore the entertainment; if user asks about technology but results include unrelated topics, ignore the unrelated topics

CRITICAL LINK EMBEDDING RULES:
- NEVER add source references as separate phrases at the end of sentences like "[source]" or "source:"
- NEVER add source names as standalone text after the main content
- NEVER use double brackets like [[source]] - this breaks markdown formatting
- ALWAYS use single brackets for markdown links: [descriptive text](URL)
- ALWAYS integrate links naturally into the flow of your sentences
- Use descriptive link text that makes sense in context
- Links should feel like natural parts of your writing, not afterthoughts
- When mentioning information, weave the source link into the sentence structure
- Make your writing flow naturally - readers should not notice the links are "added on"
- Think of links as integral parts of your narrative, not citations to be appended

LINK FORMATTING EXAMPLES:
- CORRECT: "According to [the latest AI research report](url), generative AI has attracted $33.9 billion in private investment."
- CORRECT: "The [2025 AI Index Report](url) shows that foundation models represent the latest development in this decades-old technology."
- INCORRECT: "Generative AI has attracted $33.9 billion in investment [source](url)."
- INCORRECT: "The latest research shows significant progress [[source]](url)."

SOURCE LIST REQUIREMENT:
- At the end of your response, provide a separate list of all relevant URLs with appropriate section heading in the user's language
- Use natural language to describe the format - for example, in English you might say "Related links:" or "Sources:", in Chinese you might say "相关链接：" or "参考资料：", etc.
- List each URL using Markdown link format: [descriptive text](URL)
- Each link should have a brief description of what it contains
- This provides users with easy access to all the sources you referenced

SOURCE LIST FORMAT EXAMPLE:
Related Links:
- [AWS Generative AI Overview](https://aws.amazon.com/cn/what-is/generative-ai/) - Detailed explanation of generative AI technology and applications
- [2025 AI Index Report](https://hai.stanford.edu/assets/files/hai_ai_index_report_2025_chinese_version_061325.pdf) - Latest AI development data and analysis

Please respond in the same language as the user's question and adapt all formatting accordingly."""
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute web search based on LLM-analyzed parameters.
        
        Args:
            parameters: Dictionary containing search parameters
                - query (str): Search query string
                - num_results (int, optional): Number of results to return (default: 10)
        
        Returns:
            Dictionary containing search results with the following structure:
            {
                "query": str,
                "results": List[Dict],
                "search_time": float,
                "api_source": str
            }
        """
        try:
            query = parameters.get("query", "")
            num_results = parameters.get("num_results", 10)
            
            if not query:
                return {
                    "query": "",
                    "results": [],
                    "search_time": 0.0,
                    "api_source": "google_cse",
                    "error": "No search query provided"
                }
            
            if not self.api_key or not self.engine_id:
                return {
                    "query": query,
                    "results": [],
                    "search_time": 0.0,
                    "api_source": "google_cse",
                    "error": "Google CSE API key or engine ID not configured"
                }
            
            # Perform the search
            search_results = await self._perform_search(query, num_results)
            
            return {
                "query": query,
                "results": search_results,
                "search_time": 0.0,  # Could be measured if needed
                "api_source": "google_cse"
            }
            
        except Exception as e:
            return {
                "query": parameters.get("query", ""),
                "results": [],
                "search_time": 0.0,
                "api_source": "google_cse",
                "error": f"Search tool error: {str(e)}"
            }
    
    async def _perform_search(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Perform the actual Google Custom Search API call."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {
                "key": self.api_key,
                "cx": self.engine_id,
                "q": query,
                "num": min(num_results, 10)  # Google CSE limits to 10 per request
            }
            
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract search results
            results = []
            for item in data.get("items", []):
                result = {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "source": item.get("displayLink", ""),
                    "published_date": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", "Unknown")
                }
                results.append(result)
            
            return results


# Factory function for tool creation
def create_search_tool(config: Dict[str, Any] = None) -> SearchTool:
    """Create and return a new SearchTool instance with config."""
    return SearchTool(config)
