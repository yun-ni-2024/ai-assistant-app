"""
File tool for reading and analyzing local files.
Provides file content access and intelligent analysis for various text formats.
"""

import os
from pathlib import Path
from typing import Dict, Any


class FileTool:
    """File reading and analysis tool for local filesystem files."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the file tool with configuration."""
        self.config = config or {}
        # Configuration is hardcoded in the class
        self.allowed_directory = "./data/files"
        self.allowed_extensions = [".txt", ".md", ".py", ".js", ".json", ".csv", ".html", ".css", ".yaml", ".yml", ".xml"]
        self.max_file_size = 1048576  # 1MB
        self.encoding = "utf-8"
    
    def get_tool_description(self) -> str:
        """Return a description of what this tool does."""
        return "File reading tool that can read and analyze various text format files from the local filesystem. Provides complete file content access for analysis and processing."
    
    def get_usage_conditions(self) -> str:
        """Return the conditions under which this tool should be used."""
        return """Use this tool when:
1. User provides a local file path (e.g., './data/example.txt', 'config.json', 'src/app.py')
2. User mentions 'read file', 'analyze file', 'file content', 'open file'
3. User wants to examine code files, configuration files, or documents
4. User asks about file contents, code analysis, or document structure
5. User mentions file extensions like .py, .js, .json, .md, .txt, .csv
6. User wants to analyze local files or project files
7. User asks questions about specific file contents or structure"""
    
    def get_tool_selection_prompt(self) -> str:
        """Return the prompt for tool selection analysis."""
        return f"""Tool: file
Description: {self.get_tool_description()}
Usage Conditions: {self.get_usage_conditions()}

This tool should be selected when the user wants to read or analyze a local file."""
    
    def get_parameter_extraction_prompt(self) -> str:
        """Return the prompt template for extracting file parameters from user messages."""
        return """Extract file tool parameters from the user message and conversation context.

User Message: {user_message}
Conversation Context: {conversation_context}

Extract the following parameters:
- file_id: The file ID of the uploaded file (required)

Return JSON format:
{{
    "file_id": "extracted_file_id"
}}"""
    
    def get_system_message_template(self) -> str:
        """Return the system message template for formatting file results."""
        return """I have read a file for you. Here is the file content:

{tool_result}

Please answer the user's question based on this file content: {user_message}

IMPORTANT: This file content contains REAL information that directly addresses the user's question. You MUST use this information to provide a comprehensive answer. Do NOT say you cannot provide specific data when the file content clearly contains relevant information.

Guidelines for file content analysis:
- If it's code, explain what the code does, its structure, and functionality
- If it's a document, summarize the key points and main content
- If it's data (JSON, CSV), analyze the structure and provide insights
- Always be specific and detailed in your analysis
- Use the actual file content to support your explanations"""
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute file reading based on LLM-analyzed parameters.
        
        Args:
            parameters: Dictionary containing file parameters
                - file_id (str): File ID of the uploaded file
        
        Returns:
            Dictionary containing file content with the following structure:
            {
                "file_path": str,
                "file_type": str,
                "file_size": int,
                "content": str,
                "success": bool,
                "error": str (if error occurred)
            }
        """
        try:
            file_id = parameters.get("file_id", "")
            
            if not file_id:
                return {
                    "success": False,
                    "error": "No file ID provided",
                    "file_path": "",
                    "content": "",
                    "file_type": "",
                    "file_size": 0
                }
            
            # Get file path from uploaded files mapping
            from ...api.routes.chat import _uploaded_files
            file_path = _uploaded_files.get(file_id)
            
            if not file_path or not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": "File not found or no longer available",
                    "file_path": "",
                    "content": "",
                    "file_type": "",
                    "file_size": 0
                }
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"File too large: {file_size} bytes (max: {self.max_file_size})",
                    "file_path": file_path,
                    "content": "",
                    "file_type": "",
                    "file_size": file_size
                }
            
            # Check file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.allowed_extensions:
                return {
                    "success": False,
                    "error": f"File type not allowed: {file_ext}",
                    "file_path": file_path,
                    "content": "",
                    "file_type": file_ext,
                    "file_size": file_size
                }
            
            # Read file content
            try:
                with open(file_path, 'r', encoding=self.encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                return {
                    "success": False,
                    "error": "File contains non-UTF-8 content",
                    "file_path": file_path,
                    "content": "",
                    "file_type": file_ext,
                    "file_size": file_size
                }
            
            # Clean up the uploaded file after successful processing
            self._cleanup_uploaded_file(file_id, file_path)
            
            return {
                "success": True,
                "file_path": file_path,
                "file_type": file_ext,
                "file_size": file_size,
                "content": content,
                "file_id": file_id,
                "formatted_result": f"[File Content]\nFile Path: {file_path}\nFile Type: {file_ext}\nFile Size: {file_size} bytes\n\n{content}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "file_path": parameters.get("file_path", ""),
                "content": "",
                "file_type": "",
                "file_size": 0
            }


    def _cleanup_uploaded_file(self, file_id: str, file_path: str) -> None:
        """Clean up uploaded file after processing."""
        try:
            # Get the uploaded files mapping from the chat module
            from ...api.routes.chat import _uploaded_files
            
            # Remove file from filesystem
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Cleaned up uploaded file: {file_path}")
            
            # Remove from uploaded files mapping
            if file_id in _uploaded_files:
                del _uploaded_files[file_id]
                
        except Exception as e:
            print(f"⚠️ Error cleaning up file {file_id}: {str(e)}")


def create_file_tool(config: Dict[str, Any] = None) -> FileTool:
    """Factory function to create file tool instance."""
    return FileTool(config)
