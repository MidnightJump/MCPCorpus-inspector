#!/usr/bin/env python3
"""
MCP Server Tool Extractor 
Extract tool names and descriptions from Python and TypeScript/JavaScript MCP servers
Supports various common MCP server implementation patterns
"""

import os
import re
import json
import ast
import argparse
from typing import List, Dict, Optional, Set, Union, Tuple
from pathlib import Path
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ToolInfo:
    def __init__(self, name: str, description: str = "", file_path: str = "", line_number: int = 0, pattern_type: str = "", item_type: str = "tool"):
        self.name = name
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.pattern_type = pattern_type  # For debugging, records which pattern was used
        self.item_type = item_type  # "tool", "prompt", "resource"
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "type": self.item_type,
            "file": self.file_path,
            "line": self.line_number,
            "detected_by": self.pattern_type
        }


class PythonToolExtractor:
    """Extract tool information from Python MCP servers"""
    
    def __init__(self):
        # Common MCP Python SDK patterns - more precise matching
        self.tool_patterns = [
            # Decorator patterns - stricter matching
            (r'@server\.tool\(\s*\)', "server_tool_decorator"),
            (r'@server\.tool\(\s*name\s*=', "server_tool_decorator_with_name"),
            (r'@server\.tool\(\s*description\s*=', "server_tool_decorator_with_desc"),
            (r'@app\.tool\(\s*\)', "app_tool_decorator"),
            (r'@app\.tool\(\s*name\s*=', "app_tool_decorator_with_name"),
            (r'@mcp\.tool\(\s*\)', "mcp_tool_decorator"),
            (r'@mcp\.tool\(\s*name\s*=', "mcp_tool_decorator_with_name"),
            # Only match explicit tool decorators, avoid matching other @tool decorators
            (r'@tool\(\s*name\s*=', "tool_decorator_with_name"),
            (r'@tool\(\s*description\s*=', "tool_decorator_with_desc"),
            
            # Various handler decorators
            (r'@server\.list_tools\(\s*\)', "list_tools_handler"),
            (r'@server\.call_tool\(\s*\)', "call_tool_handler"),
            (r'@server\.list_prompts\(\s*\)', "list_prompts_handler"),
            (r'@server\.get_prompt\(\s*\)', "get_prompt_handler"),
            (r'@server\.list_resources\(\s*\)', "list_resources_handler"),
            (r'@server\.read_resource\(\s*\)', "read_resource_handler"),
            
            # Schema related
            (r'ListToolsRequestSchema', "list_tools_schema"),
            (r'CallToolRequestSchema', "call_tool_schema"),
            (r'ListPromptsRequestSchema', "list_prompts_schema"),
            (r'GetPromptRequestSchema', "get_prompt_schema"),
            (r'ListResourcesRequestSchema', "list_resources_schema"),
            (r'ReadResourceRequestSchema', "read_resource_schema"),
            
            # Tool registration - more precise matching
            (r'server\.add_tool\(\s*["\']\w+["\']', "server_add_tool"),
            (r'app\.add_tool\(\s*["\']\w+["\']', "app_add_tool"),
            (r'register_tool\(\s*["\']\w+["\']', "register_tool"),
            
            # setRequestHandler patterns
            (r'server\.setRequestHandler\(\s*ListToolsRequestSchema', "set_request_handler_list_tools"),
            (r'server\.setRequestHandler\(\s*CallToolRequestSchema', "set_request_handler_call_tool"),
        ]
    
    def extract_from_file(self, file_path: str) -> List[ToolInfo]:
        """Extract tool information from Python files"""
        tools = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. First try AST parsing (most accurate)
            try:
                tree = ast.parse(content)
                ast_tools = self._extract_from_ast(tree, file_path)
                if ast_tools:
                    tools.extend(ast_tools)
                    logger.debug(f"AST found {len(ast_tools)} tools in {file_path}")
            except SyntaxError as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}")
            
            # 2. Special handling for FastMCP framework
            fastmcp_tools = self._extract_fastmcp_tools(content, file_path)
            if fastmcp_tools:
                existing_names = {tool.name for tool in tools}
                new_tools = [tool for tool in fastmcp_tools if tool.name not in existing_names]
                tools.extend(new_tools)
                logger.debug(f"FastMCP found {len(new_tools)} additional tools in {file_path}")
            
            # 3. Regex as fallback (handles cases AST cannot parse)
            regex_tools = self._extract_with_regex(content, file_path)
            if regex_tools:
                # Deduplicate (avoid AST and regex duplicates)
                existing_names = {tool.name for tool in tools}
                new_tools = [tool for tool in regex_tools if tool.name not in existing_names]
                tools.extend(new_tools)
                logger.debug(f"Regex found {len(new_tools)} additional tools in {file_path}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
        
        return tools
    
    def _extract_fastmcp_tools(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract FastMCP framework tool definitions"""
        tools = []
        
        # FastMCP patterns: @app.tool(name="tool_name", description="...")
        fastmcp_patterns = [
            # @app.tool decorator pattern
            r'@app\.tool\s*\(\s*name\s*=\s*["\']([^"\'\']+)["\']\s*(?:,\s*description\s*=\s*["\']([^"\'\']*)["\'])?\s*\)',
            r'@self\.app\.tool\s*\(\s*name\s*=\s*["\']([^"\'\']+)["\']\s*(?:,\s*description\s*=\s*["\']([^"\'\']*)["\'])?\s*\)',
        ]
        
        for pattern in fastmcp_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                name = match.group(1)
                description = match.group(2) if match.lastindex >= 2 and match.group(2) else ""
                line_number = content[:match.start()].count('\n') + 1
                
                tools.append(ToolInfo(
                    name=name,
                    description=description,
                    file_path=file_path,
                    line_number=line_number,
                    pattern_type="fastmcp_decorator"
                ))
        
        # FastMCP registration pattern - check tool list in docstrings
        docstring_tools = self._extract_from_docstring_tools_list(content, file_path)
        tools.extend(docstring_tools)
        
        return tools
    
    def _extract_from_docstring_tools_list(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract from tool list in docstrings"""
        tools = []
        
        # Find Available Tools list in docstrings
        docstring_pattern = r'"""[^"]*Available Tools:([^"]*?)"""'
        matches = re.finditer(docstring_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            tools_text = match.group(1)
            # Extract tool items (e.g.: - add_todo: Add a new todo with rich features)
            tool_items = re.finditer(r'-\s+([a-zA-Z_]\w*)\s*:\s*([^\n]+)', tools_text)
            
            for tool_match in tool_items:
                name = tool_match.group(1)
                description = tool_match.group(2).strip()
                line_number = content[:match.start()].count('\n') + tools_text[:tool_match.start()].count('\n') + 1
                
                tools.append(ToolInfo(
                    name=name,
                    description=description,
                    file_path=file_path,
                    line_number=line_number,
                    pattern_type="docstring_tools_list"
                ))
        
        return tools
    
    def _extract_from_ast(self, tree: ast.AST, file_path: str) -> List[ToolInfo]:
        """Extract tool information using AST"""
        tools = []
        
        # Find all function definitions (including async functions)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check decorators
                tool_info = self._check_function_decorators(node, file_path)
                if tool_info:
                    tools.append(tool_info)
                
                # Check if it's an MCP handler
                if self._is_mcp_handler(node):
                    handler_items = self._extract_from_mcp_handler(node, file_path)
                    tools.extend(handler_items)
            
            # Find tool registration calls
            elif isinstance(node, ast.Call):
                tool_info = self._check_tool_registration(node, file_path)
                if tool_info:
                    tools.append(tool_info)
        
        return tools
    
    def _check_function_decorators(self, func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef], file_path: str) -> Optional[ToolInfo]:
        """Check if function decorators are tool decorators"""
        for decorator in func_node.decorator_list:
            if self._is_tool_decorator(decorator):
                description = self._extract_docstring(func_node)
                return ToolInfo(
                    name=func_node.name,
                    description=description,
                    file_path=file_path,
                    line_number=func_node.lineno,
                    pattern_type="ast_decorator"
                )
        return None
    
    def _is_tool_decorator(self, decorator) -> bool:
        """Check if it's a tool decorator"""
        decorator_patterns = [
            # @tool()
            lambda d: isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'tool',
            # @server.tool(), @app.tool(), @mcp.tool()
            lambda d: isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'tool',
            # @tool (without parentheses)
            lambda d: isinstance(d, ast.Name) and d.id == 'tool',
        ]
        
        return any(pattern(decorator) for pattern in decorator_patterns)
    
    def _is_mcp_handler(self, func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
        """Check if it's an MCP handler (tools, prompts, resources)"""
        handler_names = ['list_tools', 'call_tool', 'list_prompts', 'get_prompt', 'list_resources', 'read_resource']
        
        for decorator in func_node.decorator_list:
            # Check @server.handler() pattern
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in handler_names:
                    return True
            # Check @handler() pattern
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id in handler_names:
                    return True
        return False
    
    def _get_handler_type_from_decorator(self, func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Get handler type"""
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
            elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                return decorator.func.id
        return ""
    
    def _extract_from_mcp_handler(self, func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef], file_path: str) -> List[ToolInfo]:
        """Extract items from MCP handlers (tools, prompts, resources)"""
        items = []
        handler_type = self._get_handler_type_from_decorator(func_node)
        
        # Determine item type
        if 'tool' in handler_type:
            item_type = 'tool'
        elif 'prompt' in handler_type:
            item_type = 'prompt'
        elif 'resource' in handler_type:
            item_type = 'resource'
        else:
            item_type = 'tool'  # Default to tool
        
        # Find item lists in return statements
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                handler_items = self._extract_items_from_return(node.value, file_path, item_type)
                items.extend(handler_items)
        
        return items
    
    def _extract_items_from_return(self, return_node, file_path: str, item_type: str = "tool") -> List[ToolInfo]:
        """Extract items from return statements (tools, prompts, resources)"""
        items = []
        
        # Handle direct list returns (e.g.: return [Tool(...)])
        if isinstance(return_node, ast.List):
            items.extend(self._extract_items_from_list(return_node, file_path, item_type))
        
        # Find corresponding keys in dictionaries
        elif isinstance(return_node, ast.Dict):
            for key, value in zip(return_node.keys, return_node.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.List):
                    # Determine type based on key name
                    if key.value == 'tools' or (item_type == 'tool' and key.value in ['tools']):
                        items.extend(self._extract_items_from_list(value, file_path, 'tool'))
                    elif key.value == 'prompts' or (item_type == 'prompt' and key.value in ['prompts']):
                        items.extend(self._extract_items_from_list(value, file_path, 'prompt'))
                    elif key.value == 'resources' or (item_type == 'resource' and key.value in ['resources']):
                        items.extend(self._extract_items_from_list(value, file_path, 'resource'))
        
        return items
    
    def _extract_items_from_list(self, list_node: ast.List, file_path: str, item_type: str = "tool") -> List[ToolInfo]:
        """Extract items from list nodes (tools, prompts, resources)"""
        items = []
        
        for item in list_node.elts:
            # Handle dictionary-form definitions
            if isinstance(item, ast.Dict):
                item_info = self._extract_item_from_dict(item, file_path, item_type)
                if item_info:
                    items.append(item_info)
            # Handle constructor calls (Tool(), Prompt(), Resource())
            elif isinstance(item, ast.Call):
                item_info = self._extract_item_from_call(item, file_path, item_type)
                if item_info:
                    items.append(item_info)
        
        return items
    
    def _extract_item_from_dict(self, dict_node: ast.Dict, file_path: str, item_type: str = "tool") -> Optional[ToolInfo]:
        """Extract single item information from dictionary node (generic method)"""
        name = ""
        description = ""
        
        for key, value in zip(dict_node.keys, dict_node.values):
            if isinstance(key, ast.Constant):
                if key.value == 'name' and isinstance(value, ast.Constant):
                    name = value.value
                elif key.value == 'description' and isinstance(value, ast.Constant):
                    description = value.value
        
        if name:
            return ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=dict_node.lineno if hasattr(dict_node, 'lineno') else 0,
                pattern_type=f"ast_list_{item_type}s",
                item_type=item_type
            )
        return None
    
    def _extract_item_from_call(self, call_node: ast.Call, file_path: str, item_type: str = "tool") -> Optional[ToolInfo]:
        """Extract item information from constructor calls (generic method)"""
        # Check if it's the corresponding constructor call
        constructor_names = {
            'tool': ['Tool'],
            'prompt': ['Prompt'],
            'resource': ['Resource']
        }
        
        target_names = constructor_names.get(item_type, ['Tool'])
        
        if isinstance(call_node.func, ast.Name) and call_node.func.id in target_names:
            return self._extract_from_constructor(call_node, file_path, item_type)
        elif isinstance(call_node.func, ast.Attribute) and call_node.func.attr in target_names:
            return self._extract_from_constructor(call_node, file_path, item_type)
        
        return None
    
    def _extract_from_constructor(self, call_node: ast.Call, file_path: str, item_type: str = "tool") -> Optional[ToolInfo]:
        """Extract item information from constructors (generic method)"""
        name = ""
        description = ""
        
        # Check keyword arguments
        for keyword in call_node.keywords:
            if keyword.arg == 'name' and isinstance(keyword.value, ast.Constant):
                name = keyword.value.value
            elif keyword.arg == 'description' and isinstance(keyword.value, ast.Constant):
                description = keyword.value.value
        
        # Check positional arguments (first is usually name)
        if not name and call_node.args and isinstance(call_node.args[0], ast.Constant):
            name = call_node.args[0].value
        
        if name:
            return ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=call_node.lineno,
                pattern_type=f"ast_{item_type}_constructor",
                item_type=item_type
            )
        return None
    
    def _check_tool_registration(self, call_node: ast.Call, file_path: str) -> Optional[ToolInfo]:
        """Check tool registration calls"""
        if isinstance(call_node.func, ast.Attribute) and call_node.func.attr in ['add_tool', 'register_tool']:
            return self._extract_from_call_args(call_node, file_path)
        elif isinstance(call_node.func, ast.Name) and call_node.func.id in ['add_tool', 'register_tool']:
            return self._extract_from_call_args(call_node, file_path)
        return None
    
    def _extract_from_call_args(self, call_node: ast.Call, file_path: str) -> Optional[ToolInfo]:
        """Extract tool information from function call arguments"""
        name = ""
        description = ""
        
        # Check positional arguments
        if call_node.args:
            if isinstance(call_node.args[0], ast.Constant):
                name = call_node.args[0].value
            if len(call_node.args) > 1 and isinstance(call_node.args[1], ast.Constant):
                description = call_node.args[1].value
        
        # Check keyword arguments
        for keyword in call_node.keywords:
            if keyword.arg == 'name' and isinstance(keyword.value, ast.Constant):
                name = keyword.value.value
            elif keyword.arg == 'description' and isinstance(keyword.value, ast.Constant):
                description = keyword.value.value
        
        if name:
            return ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=call_node.lineno,
                pattern_type="ast_registration"
            )
        return None
    
    def _extract_docstring(self, func_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        """Extract function docstring"""
        if (func_node.body and 
            isinstance(func_node.body[0], ast.Expr) and 
            isinstance(func_node.body[0].value, ast.Constant) and 
            isinstance(func_node.body[0].value.value, str)):
            return func_node.body[0].value.value.strip()
        return ""
    
    def _extract_with_regex(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool information using regular expressions (fallback method)"""
        tools = []
        lines = content.split('\n')
        
        # 1. Find decorator patterns
        for i, line in enumerate(lines):
            for pattern, pattern_type in self.tool_patterns:
                if re.search(pattern, line):
                    # Find next function definition
                    for j in range(i + 1, min(i + 10, len(lines))):
                        func_match = re.match(r'\s*def\s+([a-zA-Z_]\w*)', lines[j])
                        if func_match:
                            tool_name = func_match.group(1)
                            # Avoid extracting handler functions themselves
                            if tool_name in ['list_tools', 'call_tool', 'handle_tool']:
                                break
                            description = self._extract_docstring_regex(lines, j)
                            tools.append(ToolInfo(
                                name=tool_name,
                                description=description,
                                file_path=file_path,
                                line_number=j + 1,
                                pattern_type=f"regex_{pattern_type}"
                            ))
                            break
                    break
        
        # 2. Find server.tool() call patterns
        tools.extend(self._extract_server_tool_calls_python(content, file_path))
        
        # 3. Find tool list definitions
        tools.extend(self._extract_tools_list_regex(content, file_path))
        
        return tools
    
    def _extract_server_tool_calls_python(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract server.tool() calls in Python"""
        tools = []
        
        # Match server.tool("name", "description") or app.tool("name", "description") 
        tool_call_patterns = [
            r'server\.tool\s*\(\s*["\']([^"\'\']+)["\']\s*,\s*["\']([^"\'\']*)["\']',
            r'app\.tool\s*\(\s*["\']([^"\'\']+)["\']\s*,\s*["\']([^"\'\']*)["\']',
            r'mcp\.tool\s*\(\s*["\']([^"\'\']+)["\']\s*,\s*["\']([^"\'\']*)["\']',
        ]
        
        for pattern in tool_call_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                name = match.group(1)
                description = match.group(2)
                line_number = content[:match.start()].count('\n') + 1
                
                tools.append(ToolInfo(
                    name=name,
                    description=description,
                    file_path=file_path,
                    line_number=line_number,
                    pattern_type="python_server_tool_call"
                ))
        
        return tools
    
    def _extract_tools_list_regex(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool lists using regular expressions"""
        tools = []
        
        # Find tools = [...] or return {"tools": [...]}
        tool_list_patterns = [
            r'"tools":\s*\[([^\]]*)\]',
            r'tools\s*=\s*\[([^\]]*)\]',
            r'return\s*\{\s*"tools":\s*\[([^\]]*)\]',
        ]
        
        for pattern in tool_list_patterns:
            matches = re.finditer(pattern, content, re.DOTALL | re.MULTILINE)
            for match in matches:
                tools_content = match.group(1)
                extracted_tools = self._parse_tools_from_content(tools_content, file_path, match.start())
                tools.extend(extracted_tools)
        
        return tools
    
    def _parse_tools_from_content(self, tools_content: str, file_path: str, start_pos: int) -> List[ToolInfo]:
        """Parse tool content"""
        tools = []
        
        # Find tool objects {name: "...", description: "..."}
        tool_object_pattern = r'\{\s*["\']?name["\']?\s*:\s*["\']([^"\'\']*)["\']\s*,?\s*["\']?description["\']?\s*:\s*["\']([^"\'\']*)["\']\s*\}'
        
        matches = re.finditer(tool_object_pattern, tools_content)
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            
            # Calculate line number (approximate)
            line_number = tools_content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="regex_tools_list"
            ))
        
        return tools
    
    def _extract_docstring_regex(self, lines: List[str], func_line: int) -> str:
        """Extract docstring using regular expressions"""
        # Find docstring after function
        for i in range(func_line + 1, min(func_line + 10, len(lines))):
            line = lines[i].strip()
            if line.startswith('"""') or line.startswith("'''"):
                # Single-line docstring
                if line.count('"""') >= 2 or line.count("'''") >= 2:
                    return line.strip('"""').strip("'''").strip()
                # Multi-line docstring
                doc_lines = [line.strip('"""').strip("'''")]
                for j in range(i + 1, min(i + 20, len(lines))):
                    doc_line = lines[j].strip()
                    if doc_line.endswith('"""') or doc_line.endswith("'''"):
                        doc_lines.append(doc_line.rstrip('"""').rstrip("'''"))
                        return '\n'.join(doc_lines).strip()
                    doc_lines.append(doc_line)
                return '\n'.join(doc_lines).strip()
        return ""


class TypeScriptToolExtractor:
    """Extract tool information from TypeScript/JavaScript MCP servers"""
    
    def __init__(self):
        # TS/JS MCP common patterns
        self.handler_patterns = [
            (r'ListToolsRequestSchema', "list_tools_schema"),
            (r'CallToolRequestSchema', "call_tool_schema"),
            (r'ListPromptsRequestSchema', "list_prompts_schema"),
            (r'GetPromptRequestSchema', "get_prompt_schema"),
            (r'ListResourcesRequestSchema', "list_resources_schema"),
            (r'ReadResourceRequestSchema', "read_resource_schema"),
            (r'setRequestHandler.*tools/list', "set_request_handler_list"),
            (r'setRequestHandler.*tools/call', "set_request_handler_call"),
            (r'server\.setRequestHandler\s*\(\s*ListToolsRequestSchema', "server_set_request_handler_list_tools"),
            (r'server\.setRequestHandler\s*\(\s*CallToolRequestSchema', "server_set_request_handler_call_tool"),
        ]
    
    def extract_from_file(self, file_path: str) -> List[ToolInfo]:
        """Extract tool information from TypeScript/JavaScript files"""
        tools = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Multiple pattern extraction
            tools.extend(self._extract_from_tools_array(content, file_path))
            tools.extend(self._extract_from_switch_cases(content, file_path))
            tools.extend(self._extract_from_tool_objects(content, file_path))
            tools.extend(self._extract_from_functions(content, file_path))
            tools.extend(self._extract_from_request_handlers(content, file_path))
            tools.extend(self._extract_tool_schema_references(content, file_path))
            tools.extend(self._extract_create_action_decorators(content, file_path))
            tools.extend(self._extract_tool_constants(content, file_path))
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
        
        # Smart deduplication - keep most accurate detection results
        return self._deduplicate_tools(tools)
    
    def _extract_from_tools_array(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool array definitions"""
        tools = []
        
        # Multiple tool array patterns
        array_patterns = [
            r'tools\s*:\s*\[(.*?)\]',
            r'const\s+tools\s*=\s*\[(.*?)\]',
            r'return\s*\{\s*tools\s*:\s*\[(.*?)\]',
            r'ListToolsRequestSchema[^{]*\{\s*return\s*\{\s*tools\s*:\s*\[(.*?)\]',
        ]
        
        for pattern in array_patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                tools_content = match.group(1)
                line_number = content[:match.start()].count('\n') + 1
                extracted_tools = self._parse_tool_objects(tools_content, file_path, line_number)
                for tool in extracted_tools:
                    tool.pattern_type = "ts_tools_array"
                tools.extend(extracted_tools)
        
        return tools
    
    def _extract_from_tool_objects(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract single tool object definitions"""
        tools = []
        
        # Match tool objects {name: "...", description: "..."}
        object_pattern = r'\{\s*name\s*:\s*["\']([^"\'\']+)["\']\s*,\s*description\s*:\s*["\']([^"\'\']*)["\']'
        
        matches = re.finditer(object_pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="ts_tool_object"
            ))
        
        return tools
    
    def _extract_from_switch_cases(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool names from switch statements"""
        tools = []
        
        # Common non-tool case names
        excluded_cases = {
            'default', 'error', 'success', 'fail', 'init', 'start', 'stop', 
            'pause', 'resume', 'reset', 'clear', 'update', 'refresh', 'reload',
            'get', 'set', 'add', 'remove', 'delete', 'create', 'destroy',
            'open', 'close', 'connect', 'disconnect', 'login', 'logout',
            'true', 'false', 'yes', 'no', 'on', 'off', '0', '1'
        }
        
        # Find tool names in switch cases
        switch_pattern = r"case\s+[\"\']([^\"\'\']*)[\"\']:"
        
        matches = re.finditer(switch_pattern, content)
        for match in matches:
            tool_name = match.group(1)
            
            # Skip obviously non-tool cases
            if (tool_name.lower() in excluded_cases or 
                len(tool_name) < 2 or 
                tool_name.isdigit() or
                not tool_name.replace('_', '').replace('-', '').isalnum()):
                continue
            
            # Check if in tool handling context
            context_start = max(0, match.start() - 500)
            context_end = min(len(content), match.end() + 500)
            context = content[context_start:context_end].lower()
            
            # Must contain tool-related context keywords
            tool_context_keywords = ['tool', 'mcp', 'request', 'handler', 'call']
            if not any(keyword in context for keyword in tool_context_keywords):
                continue
            
            line_number = content[:match.start()].count('\n') + 1
            
            # Find nearby comments as description
            description = self._find_nearby_comment(content, match.start())
            
            # Only add if description is not empty or tool name looks like a real tool
            if description or self._looks_like_tool_name(tool_name):
                tools.append(ToolInfo(
                    name=tool_name,
                    description=description,
                    file_path=file_path,
                    line_number=line_number,
                    pattern_type="ts_switch_case"
                ))
        
        return tools
    
    def _looks_like_tool_name(self, name: str) -> bool:
        """Check if name looks like a tool name"""
        # Tool names usually contain verbs or descriptive words
        tool_indicators = [
            'get', 'set', 'create', 'delete', 'update', 'fetch', 'send', 'read', 'write',
            'search', 'find', 'list', 'show', 'display', 'generate', 'process', 'execute',
            'run', 'start', 'stop', 'check', 'validate', 'parse', 'format', 'convert',
            'calculate', 'compute', 'analyze', 'scan', 'monitor', 'track', 'log'
        ]
        
        name_lower = name.lower()
        return (any(indicator in name_lower for indicator in tool_indicators) or
                len(name) > 5)  # Longer names are more likely to be tools
    
    def _extract_from_functions(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract possible tools from function names"""
        tools = []
        
        # 1. First extract server.tool() call patterns
        tools.extend(self._extract_server_tool_calls(content, file_path))
        
        # 2. Find async functions that might be tools
        func_patterns = [
            r'async\s+function\s+([a-zA-Z_]\w*)',
            r'const\s+([a-zA-Z_]\w*)\s*=\s*async',
            r'([a-zA-Z_]\w*)\s*:\s*async\s+\(',
        ]
        
        # Extended excluded function names list
        excluded_names = {
            'main', 'init', 'setup', 'start', 'run', 'handleListTools', 'handleCallTool', 
            'listTools', 'callTool', 'connect', 'disconnect', 'close', 'open', 'create',
            'update', 'delete', 'get', 'set', 'fetch', 'send', 'receive', 'process',
            'handle', 'execute', 'validate', 'parse', 'format', 'transform', 'convert',
            'load', 'save', 'read', 'write', 'check', 'test', 'verify', 'authenticate',
            'authorize', 'login', 'logout', 'register', 'unregister', 'subscribe',
            'unsubscribe', 'publish', 'emit', 'listen', 'watch', 'monitor', 'log',
            'debug', 'error', 'warn', 'info', 'trace', 'cleanup', 'dispose', 'destroy',
            # Add more obvious internal functions
            'validatePath', 'getFileStats', 'readFileAsBase64Stream', 'runServer',
            'updateAllowedDirectoriesFromRoots', 'tailFile', 'headFile', 'constructBaseScanUrl',
            'generateSessionId', 'postMetric', 'getMorphoVaults', 'detectStandardAndTransferNft',
            # Add common Helper function patterns
            'getRawTextString', 'getHtmlString', 'getMarkdownStringFromHtmlByTD', 'getMarkdownStringFromHtmlByNHM'
        }
        
        # Tool-related keywords
        tool_keywords = ['tool', 'command', 'action', 'operation', 'task', 'job', 'work']
        
        for pattern in func_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                func_name = match.group(1)
                
                # Basic filtering conditions
                if func_name in excluded_names or func_name.startswith('_'):
                    continue
                
                # Check if function name looks like a tool name
                if not self._looks_like_tool_name(func_name):
                    continue
                
                # Get function context
                start_pos = max(0, match.start() - 200)
                end_pos = min(len(content), match.end() + 200)
                context = content[start_pos:end_pos].lower()
                
                # Check if it's obviously a helper function
                if self._is_helper_function(func_name, context):
                    continue
                
                has_tool_context = any(keyword in context for keyword in tool_keywords)
                
                # Check if there are meaningful comments or documentation
                description = self._find_nearby_comment(content, match.start())
                has_meaningful_description = description and len(description.strip()) > 10
                
                # Only consider as tool if has tool context or meaningful description
                if has_tool_context or has_meaningful_description:
                    line_number = content[:match.start()].count('\n') + 1
                    
                    tools.append(ToolInfo(
                        name=func_name,
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        pattern_type="ts_function"
                    ))
        
        return tools
    
    def _extract_server_tool_calls(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract server.tool() calls"""
        tools = []
        
        # Match server.tool("name", "description", ...) pattern
        # Support multi-line matching and nested parentheses
        tool_call_pattern = r'server\.tool\s*\(\s*["\']([^"\'\']+)["\']\s*,\s*["\']([^"\'\']*)["\']'
        
        matches = re.finditer(tool_call_pattern, content, re.MULTILINE | re.DOTALL)
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="ts_server_tool_call"
            ))
        
        return tools
    
    def _parse_tool_objects(self, tools_content: str, file_path: str, base_line: int) -> List[ToolInfo]:
        """Parse tool objects"""
        tools = []
        
        # Split tool objects (by },{ )
        tool_objects = re.split(r'\},\s*\{', tools_content)
        
        for i, obj in enumerate(tool_objects):
            # Clean object string
            obj = obj.strip().strip('{').strip('}')
            
            # Extract name and description
            name_match = re.search(r'name\s*:\s*["\']([^"\'\']+)["\']', obj)
            desc_match = re.search(r'description\s*:\s*["\']([^"\'\']*)["\']', obj)
            
            if name_match:
                name = name_match.group(1)
                description = desc_match.group(1) if desc_match else ""
                
                # Calculate line number offset
                line_offset = obj[:name_match.start()].count('\n') if name_match else 0
                
                tools.append(ToolInfo(
                    name=name,
                    description=description,
                    file_path=file_path,
                    line_number=base_line + line_offset,
                    pattern_type="ts_parsed_object"
                ))
        
        return tools
    
    def _find_nearby_comment(self, content: str, position: int) -> str:
        """Find comments near specified position"""
        lines = content[:position].split('\n')
        
        # Look up for comments
        for i in range(len(lines) - 1, max(0, len(lines) - 5), -1):
            line = lines[i].strip()
            if line.startswith('//'):
                return line.lstrip('/').strip()
            elif line.startswith('/*') and line.endswith('*/'):
                return line.strip('/*').strip()
        
        return ""
    
    def _extract_from_request_handlers(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tools from TypeScript setRequestHandler patterns"""
        tools = []
        
        # Find server.setRequestHandler(ListToolsRequestSchema, ...) 
        list_tools_pattern = r'server\.setRequestHandler\s*\(\s*ListToolsRequestSchema\s*,\s*async\s*\([^)]*\)\s*=>\s*\{([^}]*?tools\s*:\s*\[([^\]]*)\])?[^}]*\}'
        
        matches = re.finditer(list_tools_pattern, content, re.DOTALL | re.MULTILINE)
        for match in matches:
            line_number = content[:match.start()].count('\n') + 1
            
            if match.group(2):  # Found tools array
                tools_content = match.group(2)
                extracted_tools = self._parse_tool_objects(tools_content, file_path, line_number)
                for tool in extracted_tools:
                    tool.pattern_type = "ts_set_request_handler"
                tools.extend(extracted_tools)
        
        # Find simple tools array return patterns
        simple_tools_pattern = r'return\s*\{\s*tools\s*:\s*\[([^\]]*)\]'
        
        matches = re.finditer(simple_tools_pattern, content, re.DOTALL | re.MULTILINE)
        for match in matches:
            tools_content = match.group(1)
            line_number = content[:match.start()].count('\n') + 1
            extracted_tools = self._parse_tool_objects(tools_content, file_path, line_number)
            for tool in extracted_tools:
                tool.pattern_type = "ts_simple_return"
            tools.extend(extracted_tools)
        
        return tools
    
    def _extract_tool_schema_references(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool pattern references in TypeScript"""
        tools = []
        
        # Find inputSchema references (e.g.: inputSchema: zodToJsonSchema(ReadTextFileArgsSchema))
        schema_pattern = r'\{\s*name\s*:\s*["\']([^"\'\']+)["\']\s*,\s*description\s*:\s*["\']([^"\'\']*)["\'][^}]*inputSchema\s*:[^}]*\}'
        
        matches = re.finditer(schema_pattern, content, re.DOTALL | re.MULTILINE)
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="ts_schema_reference"
            ))
        
        return tools
    
    def _deduplicate_tools(self, tools: List[ToolInfo]) -> List[ToolInfo]:
        """Smart deduplication, keep most accurate detection results"""
        # Group by name
        by_name = {}
        for tool in tools:
            key = tool.name
            if key not in by_name:
                by_name[key] = []
            by_name[key].append(tool)
        
        # Select best detection result for each tool name
        unique_tools = []
        for tool_name, tool_list in by_name.items():
            if len(tool_list) == 1:
                unique_tools.append(tool_list[0])
            else:
                # Select best result based on detection pattern priority
                best_tool = self._select_best_detection(tool_list)
                unique_tools.append(best_tool)
        
        return unique_tools
    
    def _select_best_detection(self, tools: List[ToolInfo]) -> ToolInfo:
        """Select most accurate one from multiple detection results"""
        # Detection pattern priority (high to low)
        priority_order = [
            "ts_create_action_decorator",  # Coinbase AgentKit
            "ast_tool_constructor",        # MCP SDK Tool()
            "ast_prompt_constructor",      # MCP SDK Prompt()
            "ast_resource_constructor",    # MCP SDK Resource()
            "ts_tool_constant",           # TypeScript tool constants
            "fastmcp_decorator",          # FastMCP decorators
            "ast_decorator",              # General decorators
            "ts_set_request_handler",     # TypeScript setRequestHandler
            "ts_tools_array",             # Tool arrays
            "ts_tool_object",             # Tool objects
            "ts_schema_reference",        # Schema references
            "ts_simple_return",           # Simple returns
            "ts_switch_case",             # Switch cases
            "ts_function",                # Function heuristics
            "docstring_tools_list",       # Docstring lists
            "regex_tools_list",           # Regular expressions
        ]
        
        # Find tool with highest priority
        for pattern in priority_order:
            for tool in tools:
                if tool.pattern_type == pattern:
                    return tool
        
        # If no matching priority, return the one with most detailed description
        return max(tools, key=lambda t: len(t.description or ""))
    
    def _extract_create_action_decorators(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract @CreateAction decorators in TypeScript"""
        tools = []
        
        # Match @CreateAction decorator pattern
        create_action_pattern = r'@CreateAction\s*\(\s*\{\s*name:\s*["\']([^"\'\']+)["\']\s*,\s*description:\s*["\']([^"\'\']*)["\']'
        
        matches = re.finditer(create_action_pattern, content, re.DOTALL | re.MULTILINE)
        for match in matches:
            name = match.group(1)
            description = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="ts_create_action_decorator"
            ))
        
        return tools
    
    def _is_helper_function(self, func_name: str, context: str) -> bool:
        """Check if it's a helper function"""
        # Common patterns for helper functions
        helper_patterns = [
            r'helper\s+method',
            r'utility\s+function', 
            r'internal\s+function',
            r'private\s+function',
            r'//\s*helper',
            r'/\*\*\s*helper',
            r'export\s+async\s+function.*helper',
            r'function.*helper',
        ]
        
        # Check function name patterns
        helper_name_patterns = [
            r'.*helper.*',
            r'.*util.*',
            r'.*internal.*',
            r'get.*string',  # getXXXString are usually helper functions
            r'.*from.*by.*', # e.g.: getMarkdownStringFromHtmlByTD
        ]
        
        # Check for Helper indicators in context
        for pattern in helper_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return True
        
        # Check function name patterns
        for pattern in helper_name_patterns:
            if re.match(pattern, func_name, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_tool_constants(self, content: str, file_path: str) -> List[ToolInfo]:
        """Extract tool constant definitions in TypeScript"""
        tools = []
        
        # Match tool constant patterns (e.g.: const SEQUENTIAL_THINKING_TOOL: Tool = {name: "...", description: "..."})
        tool_constant_pattern = r'const\s+(\w*TOOL\w*)\s*:\s*Tool\s*=\s*\{\s*name\s*:\s*["\']([^"\'\']+)["\'].*?description\s*:\s*["\']([^"\'\']*?)["\']'
        
        matches = re.finditer(tool_constant_pattern, content, re.DOTALL | re.MULTILINE)
        for match in matches:
            constant_name = match.group(1)
            tool_name = match.group(2)
            description = match.group(3)
            line_number = content[:match.start()].count('\n') + 1
            
            tools.append(ToolInfo(
                name=tool_name,
                description=description,
                file_path=file_path,
                line_number=line_number,
                pattern_type="ts_tool_constant"
            ))
        
        return tools


class MCPToolExtractor:
    """Main extractor class"""
    
    def __init__(self, verbose: bool = False):
        self.python_extractor = PythonToolExtractor()
        self.ts_extractor = TypeScriptToolExtractor()
        self.supported_extensions = {'.py', '.ts', '.js', '.mts', '.mjs'}
        self.verbose = verbose
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def extract_from_directory(self, directory: str) -> List[ToolInfo]:
        """Extract all tool information from directory"""
        all_tools = []
        file_count = 0
        
        for root, dirs, files in os.walk(directory):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'node_modules', '.git', '__pycache__', 'dist', 'build', '.venv'}]
            
            for file in files:
                file_path = os.path.join(root, file)
                if self._is_supported_file(file_path):
                    file_count += 1
                    tools = self.extract_from_file(file_path)
                    if tools:
                        logger.info(f"Found {len(tools)} tools in {file_path}")
                        all_tools.extend(tools)
        
        logger.info(f"Scanned {file_count} files, found {len(all_tools)} tools total")
        return all_tools
    
    def extract_from_file(self, file_path: str) -> List[ToolInfo]:
        """Extract tool information from single file"""
        ext = Path(file_path).suffix.lower()
        
        try:
            tools = []
            if ext == '.py':
                tools = self.python_extractor.extract_from_file(file_path)
            elif ext in {'.ts', '.js', '.mts', '.mjs'}:
                tools = self.ts_extractor.extract_from_file(file_path)
            
            # Validate and filter tools
            return self._validate_tools(tools)
        except Exception as e:
            logger.error(f"Failed to extract from {file_path}: {e}")
        
        return []

    def _validate_tools(self, tools: List[ToolInfo]) -> List[ToolInfo]:
        """Validate tool validity, filter out invalid tools"""
        valid_tools = []
        
        for tool in tools:
            if self._is_valid_tool(tool):
                valid_tools.append(tool)
            elif self.verbose:
                logger.debug(f"Filtered out invalid tool: {tool.name} (no valid description)")
        
        return valid_tools
    
    def _is_valid_tool(self, tool: ToolInfo) -> bool:
        """Check if item is valid (tools, prompts, resources)"""
        # Check if name is valid
        if not tool.name or not tool.name.strip():
            return False
        
        # Check name format
        name = tool.name.strip()
        if not self._is_valid_name(name):
            return False
        
        # For certain detection patterns, allow items without description
        relaxed_patterns = [
            "ast_tool_constructor", "ast_prompt_constructor", "ast_resource_constructor",
            "ast_list_tools", "ast_list_prompts", "ast_list_resources",
            "fastmcp_decorator", "ts_set_request_handler"
        ]
        
        if tool.pattern_type in relaxed_patterns:
            return True
        
        # Check if description is valid
        if not tool.description or not tool.description.strip():
            return False
        
        # Description length check (different types may have different requirements)
        description = tool.description.strip()
        min_length = 3
        
        if len(description) < min_length:
            return False
        
        return True
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if name format is valid"""
        # Basic format check
        if not name.replace('_', '').replace('-', '').isalnum():
            return False
        
        # Length check
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Cannot be pure numbers
        if name.isdigit():
            return False
        
        return True
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file is supported"""
        return Path(file_path).suffix.lower() in self.supported_extensions


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Extract tool information from MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_en.py /path/to/mcp/server
  python test_en.py /path/to/mcp/server --output tools.json
  python test_en.py /path/to/mcp/server --verbose
        """
    )
    
    parser.add_argument(
        'directory',
        help='MCP server directory path'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output JSON file path (default: output to stdout)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'table', 'list'],
        default='json',
        help='Output format (default: json)'
    )
    
    args = parser.parse_args()
    
    # Check if directory exists
    if not os.path.exists(args.directory):
        logger.error(f"Directory does not exist: {args.directory}")
        return 1
    
    if not os.path.isdir(args.directory):
        logger.error(f"Path is not a directory: {args.directory}")
        return 1
    
    # Create extractor
    extractor = MCPToolExtractor(verbose=args.verbose)
    
    # Extract tools
    logger.info(f"Scanning directory: {args.directory}")
    tools = extractor.extract_from_directory(args.directory)
    
    # Output results
    if args.format == 'json':
        output_data = [tool.to_dict() for tool in tools]
        json_output = json.dumps(output_data, indent=2, ensure_ascii=False)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            logger.info(f"Results saved to: {args.output}")
        else:
            print(json_output)
    
    elif args.format == 'table':
        if tools:
            print(f"{'Name':<30} {'Type':<10} {'File':<50} {'Line':<6} {'Description':<50}")
            print("-" * 146)
            for tool in tools:
                print(f"{tool.name:<30} {tool.item_type:<10} {tool.file_path:<50} {tool.line_number:<6} {tool.description[:47]+'...' if len(tool.description) > 50 else tool.description:<50}")
        else:
            print("No tools found.")
    
    elif args.format == 'list':
        if tools:
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")
        else:
            print("No tools found.")
    
    logger.info(f"Total found: {len(tools)} tools")
    return 0


if __name__ == '__main__':
    exit(main())
