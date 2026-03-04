import inspect
import json
import logging
import os
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel

from src.core.constants import TOOL_CALL_OPEN, TOOL_CALL_CLOSE, TOOL_OUTPUT_TRUNCATED_MARKER
from src.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission Roles (ordered by privilege level)
# ---------------------------------------------------------------------------
ROLE_PUBLIC = "public"    # Any client, including guests
ROLE_USER = "user"        # Authenticated standard users
ROLE_ADMIN = "admin"      # Full-privilege administrators

ROLE_HIERARCHY = {ROLE_PUBLIC: 0, ROLE_USER: 1, ROLE_ADMIN: 2}

# Placeholder tool name used in the no-args example inside the system prompt
_EXAMPLE_NO_ARG_TOOL = "get_current_time"


class ToolPermissionError(Exception):
    """Raised when a client lacks the required role to execute a tool."""
    pass


class ToolManager:
    """Manages the registration, permission gating, and execution of tools."""
    
    def __init__(self, max_output_chars: int = settings.TOOL_MAX_OUTPUT_CHARS):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._permissions: Dict[str, str] = {}          # tool_name → required role
        self._client_roles: Dict[Any, str] = {}         # client_id → assigned role
        self.max_output_chars = max_output_chars
        
    # ------------------------------------------------------------------
    # Client role management
    # ------------------------------------------------------------------
    def set_client_role(self, client_id: Any, role: str):
        """Assigns a permission role to a client_id."""
        if role not in ROLE_HIERARCHY:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {list(ROLE_HIERARCHY.keys())}")
        self._client_roles[client_id] = role
        
    def get_client_role(self, client_id: Any) -> str:
        """Returns the role for a client, defaulting to 'public'."""
        return self._client_roles.get(client_id, ROLE_PUBLIC)
        
    def _check_permission(self, client_id: Any, tool_name: str):
        """Raises ToolPermissionError if client lacks the required role."""
        required = self._permissions.get(tool_name, ROLE_PUBLIC)
        actual = self.get_client_role(client_id)
        if ROLE_HIERARCHY.get(actual, 0) < ROLE_HIERARCHY.get(required, 0):
            raise ToolPermissionError(
                f"Client '{client_id}' (role={actual}) lacks permission for tool "
                f"'{tool_name}' (requires={required})."
            )
    
    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------
    def register(self, func: Callable, required_role: str = ROLE_PUBLIC):
        """Registers a tool function with an optional required permission role."""
        name = func.__name__
        self._tools[name] = func
        self._permissions[name] = required_role
        
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
            "parameters": params,
            "required_role": required_role,
        }
        
        self._schemas[name] = schema
        return func
        
    def get_tool_schemas(self, client_id: Any = None) -> List[Dict[str, Any]]:
        """Returns the JSON schemas for tools accessible to a given client.
        
        If client_id is None, returns all schemas (for internal use).
        If client_id is provided, filters by the client's role.
        """
        if client_id is None:
            return list(self._schemas.values())
            
        client_role_level = ROLE_HIERARCHY.get(self.get_client_role(client_id), 0)
        return [
            s for s in self._schemas.values()
            if ROLE_HIERARCHY.get(s.get("required_role", ROLE_PUBLIC), 0) <= client_role_level
        ]
    
    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------
    async def execute_tool(self, name: str, client_id: Any = None, **kwargs) -> Any:
        """Executes a registered tool with permission check and output cap.
        
        Args:
            name: Tool function name.
            client_id: Caller's client ID for permission validation.
            **kwargs: Arguments forwarded to the tool function.
            
        Raises:
            ValueError: If the tool is not registered.
            ToolPermissionError: If the client lacks the required role.
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found.")
            
        # Permission gate
        if client_id is not None:
            self._check_permission(client_id, name)
        
        func = self._tools[name]
        
        # Execute
        if inspect.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)
            
        # Output size limit — cap to prevent context overflow
        result_str = result if isinstance(result, str) else json.dumps(result)
        if len(result_str) > self.max_output_chars:
            logger.warning(
                f"Tool '{name}' output truncated: {len(result_str)} → {self.max_output_chars} chars"
            )
            result_str = result_str[:self.max_output_chars] + TOOL_OUTPUT_TRUNCATED_MARKER
            return result_str
            
        return result

    # ------------------------------------------------------------------
    # System prompt & grammar generation
    # ------------------------------------------------------------------
    def _format_tool_signature(self, schema: dict) -> str:
        """Format a tool schema as: tool_name(param1: type, param2: type) - description

        Example: "web_search(query: string) - Search the web using DuckDuckGo"
        """
        name = schema["name"]
        description = schema.get("description", "")
        props = schema.get("parameters", {}).get("properties", {})
        params_str = ", ".join(
            f"{p}: {info.get('type', 'string')}"
            for p, info in props.items()
        )
        return f"{name}({params_str}) - {description}"

    def get_system_prompt_addition(self, client_id: Any = None) -> str:
        """Generates a system prompt describing available tools for this client."""
        schemas = self.get_tool_schemas(client_id)
        if not schemas:
            return ""

        tool_list = "\n".join(
            f"{i + 1}. {self._format_tool_signature(s)}"
            for i, s in enumerate(schemas)
        )

        # Use a real tool for Example 2 when available, else fall back to placeholders
        example_tool = schemas[0]
        example_name = example_tool["name"]
        example_props = example_tool.get("parameters", {}).get("properties", {})
        if example_props:
            first_param = next(iter(example_props))
            example_args = json.dumps({first_param: f"<{first_param}_value>"}, indent=2)
        else:
            example_args = "{}"

        return (
            "You are a helpful AI assistant with access to tools for real-time information.\n\n"
            "AVAILABLE TOOLS:\n"
            f"{tool_list}\n\n"
            "HOW TO USE TOOLS:\n"
            "When you need real-time or external data, output a tool call in this EXACT format:\n\n"
            f"{TOOL_CALL_OPEN}\n"
            "{\n"
            '  "name": "tool_name",\n'
            '  "arguments": {\n'
            '    "param1": "value1"\n'
            "  }\n"
            "}\n"
            f"{TOOL_CALL_CLOSE}\n\n"
            "EXAMPLES:\n\n"
            "Example 1 - No arguments:\n"
            "User: What time is it?\n"
            f"Assistant: {TOOL_CALL_OPEN}\n"
            "{\n"
            f'  "name": "{_EXAMPLE_NO_ARG_TOOL}",\n'
            '  "arguments": {}\n'
            "}\n"
            f"{TOOL_CALL_CLOSE}\n\n"
            "Example 2 - With arguments:\n"
            "User: Search for Python tutorials\n"
            f"Assistant: {TOOL_CALL_OPEN}\n"
            "{\n"
            f'  "name": "{example_name}",\n'
            f'  "arguments": {example_args}\n'
            "}\n"
            f"{TOOL_CALL_CLOSE}\n\n"
            "IMPORTANT RULES:\n"
            "1. Use tools ONLY when you need current/external data\n"
            "2. Output ONLY the tool call, nothing before or after\n"
            "3. Wait for the tool result before responding\n"
            "4. After receiving results, synthesize a natural answer\n"
            "5. NEVER invent information - use tools if uncertain"
        )
        
    def generate_gbnf_grammar(self, client_id: Any = None) -> str:
        """Generates a strict GBNF grammar string based on the tools available to this client."""
        # [DEPRECATED] Use system prompt instead. Enable with ENABLE_GBNF_GRAMMAR=true
        if not os.getenv("ENABLE_GBNF_GRAMMAR", "").lower() == "true":
            return ""

        schemas = self.get_tool_schemas(client_id)
        if not schemas:
            return ""
            
        grammar = r'''
root ::= (text | tool_call)*
text ::= [^<]+
tool_call ::= "<tool_call>" ws tool_choice ws "</tool_call>"
'''
        
        tool_choices = []
        
        for i, schema in enumerate(schemas):
            name = schema["name"]
            params = schema["parameters"].get("properties", {})
            
            rule_name = f"tool_{i}"
            tool_choices.append(rule_name)
            
            args_parts = []
            for prop_name, prop_data in params.items():
                if prop_data.get("type") in ["integer", "number"]:
                    val_rule = "number"
                elif prop_data.get("type") == "boolean":
                    val_rule = "boolean"
                elif prop_data.get("type") == "array":
                    val_rule = "array"
                else:
                    val_rule = "string"
                    
                prop_rule = f'ws "\\"{prop_name}\\"" ws ":" ws {val_rule}'
                args_parts.append(prop_rule)
                
            if args_parts:
                args_str = f' ws "," ws '.join(args_parts)
                args_rule = f'"\\"arguments\\":" ws "{{" {args_str} ws "}}"'
            else:
                args_rule = f'"\\"arguments\\":" ws "{{}}"'
                
            rule_def = f'{rule_name} ::= "{{\\"name\\": \\"{name}\\", " ws {args_rule} ws "}}"'
            grammar += f"\n{rule_def}"
            
        grammar += f"\n\ntool_choice ::= {' | '.join(tool_choices)}\n"
        
        grammar += r'''
boolean ::= "true" | "false"
string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
array ::= "[" ws (string (ws "," ws string)*)? ws "]"
ws ::= [ \t\n\r]*
'''
        return grammar.strip()

# Global ToolManager instance
tool_manager = ToolManager()

def tool(func: Callable = None, *, required_role: str = ROLE_PUBLIC):
    """Decorator to register a function as a tool.
    
    Usage:
        @tool                           # public tool (any client)
        async def search(query: str): ...
        
        @tool(required_role="admin")    # admin-only tool
        async def gpu_stats(): ...
    """
    if func is not None:
        # Called as @tool without arguments
        return tool_manager.register(func, required_role=ROLE_PUBLIC)
    
    # Called as @tool(required_role="admin")
    def decorator(f: Callable):
        return tool_manager.register(f, required_role=required_role)
    return decorator

