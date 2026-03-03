import inspect
import json
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel

class ToolManager:
    """Manages the registration and execution of tools."""
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        
    def register(self, func: Callable):
        """Registers a tool function."""
        name = func.__name__
        self._tools[name] = func
        
        # Parse docstring for description
        doc = inspect.getdoc(func)
        description = doc.split('\n')[0] if doc else f"Tool: {name}"
        
        # Parse signature for parameters
        sig = inspect.signature(func)
        params = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
                
            param_type = "string" # Default
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_type = "array"
                elif param.annotation == dict or param.annotation == Dict:
                    param_type = "object"
            
            params["properties"][param_name] = {"type": param_type}
            
            if param.default == inspect.Parameter.empty:
                params["required"].append(param_name)
                
        schema = {
            "name": name,
            "description": description,
            "parameters": params
        }
        
        self._schemas[name] = schema
        return func
        
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns the JSON schemas for all registered tools."""
        return list(self._schemas.values())
        
    async def execute_tool(self, name: str, **kwargs) -> Any:
        """Executes a registered tool with the given arguments."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found.")
            
        func = self._tools[name]
        
        # Check if it's an async function
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        else:
            return func(**kwargs)

# Global ToolManager instance
tool_manager = ToolManager()

def tool(func: Callable):
    """Decorator to register a function as a tool."""
    return tool_manager.register(func)
