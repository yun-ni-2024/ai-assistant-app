"""
Tool Registry for managing MCP tools configuration and instantiation.
Loads tool configurations from YAML file and provides unified access.
"""

import yaml
import importlib
from typing import Dict, Any, List, Optional
from pathlib import Path


class ToolRegistry:
    """Registry for managing MCP tools configuration and instantiation."""
    
    def __init__(self, config_path: str = None):
        """Initialize the tool registry with configuration file."""
        if config_path is None:
            # Default to tools_config.yaml in the same directory
            current_dir = Path(__file__).parent
            config_path = current_dir / "tools_config.yaml"
        
        self.config_path = config_path
        self.tools_config = self._load_config()
        self._tool_instances = {}  # Cache for tool instances
    
    def _load_config(self) -> Dict[str, Any]:
        """Load tool configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            return config.get('tools', {})
        except Exception as e:
            print(f"🔧 Error loading tools config: {str(e)}")
            return {}
    
    def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all available tools configuration."""
        return {name: config for name, config in self.tools_config.items() 
                if config.get('enabled', True)}
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific tool."""
        return self.tools_config.get(tool_name)
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled."""
        tool_config = self.get_tool_config(tool_name)
        return tool_config.get('enabled', True) if tool_config else False
    
    def get_tool_class(self, tool_name: str):
        """Get tool class for a specific tool."""
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None
        
        try:
            # Import the module
            module_path = tool_config['class_module']
            
            # Handle relative imports
            if module_path.startswith('.'):
                # Get the current package (backend.app.services.tools)
                current_package = __package__
                # Convert relative import to absolute
                module_path = f"{current_package}{module_path}"
            
            module = importlib.import_module(module_path)
            
            # Get the class
            class_name = tool_config['class_name']
            tool_class = getattr(module, class_name)
            
            return tool_class
        except Exception as e:
            print(f"🔧 Error getting tool class for {tool_name}: {str(e)}")
            return None
    
    def create_tool_instance(self, tool_name: str):
        """Create a tool instance for a specific tool."""
        # Check cache first
        if tool_name in self._tool_instances:
            return self._tool_instances[tool_name]
        
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None
        
        try:
            # Import the module
            module_path = tool_config['class_module']
            
            # Handle relative imports
            if module_path.startswith('.'):
                # Get the current package (backend.app.services.tools)
                current_package = __package__
                # Convert relative import to absolute
                module_path = f"{current_package}{module_path}"
            
            module = importlib.import_module(module_path)
            
            # Get the factory function
            factory_function_name = tool_config['factory_function']
            factory_function = getattr(module, factory_function_name)
            
            # Get tool-specific config
            config = tool_config.get('config', {})
            
            # Create instance with config
            instance = factory_function(config)
            
            # Cache the instance
            self._tool_instances[tool_name] = instance
            
            return instance
        except Exception as e:
            print(f"🔧 Error creating tool instance for {tool_name}: {str(e)}")
            return None
    
    def get_tool_instance(self, tool_name: str):
        """Get tool instance for a specific tool (cached)."""
        return self.create_tool_instance(tool_name)
    
    def get_tool_description_for_selection(self) -> List[Dict[str, Any]]:
        """Get tool descriptions formatted for LLM tool selection."""
        available_tools = self.get_available_tools()
        descriptions = []
        
        for tool_name, config in available_tools.items():
            descriptions.append({
                "name": config.get("name", tool_name),
                "description": config.get("description", ""),
                "use_cases": config.get("use_cases", [])
            })
        
        return descriptions


# Global tool registry instance
_tool_registry = None

def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
