"""Main FastMCP server for Workoflow platform integration."""

import json
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from workoflow_mcp.cache import get_cache
from workoflow_mcp.client import get_client

# Load environment variables
load_dotenv()

# Get tool types filter from environment
TOOL_TYPES = os.getenv("TOOL_TYPES", "")


def get_prompt_token() -> str | None:
    """Extract X-Prompt-Token from current request headers."""
    headers = get_http_headers()

    # Try X-Prompt-Token header first
    token = headers.get("x-prompt-token")
    if token:
        return token

    # Try Authorization: Bearer header
    auth_header = headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]

    return None


@asynccontextmanager
async def lifespan(app: FastMCP):
    """Manage server lifecycle - setup and teardown."""
    # Startup: Initialize tracing if configured
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otel_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({
                "service.name": os.getenv("OTEL_SERVICE_NAME", "workoflow-mcp"),
            })
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=f"{otel_endpoint}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            print(f"OpenTelemetry tracing enabled, exporting to {otel_endpoint}")
        except ImportError:
            print("OpenTelemetry packages not installed, tracing disabled")
        except Exception as e:
            print(f"Failed to initialize OpenTelemetry: {e}")

    yield

    # Shutdown: Close HTTP client
    client = get_client()
    await client.close()


# Create the FastMCP server
mcp = FastMCP(
    name="workoflow-mcp",
    instructions="""
    Workoflow MCP Server - Bridge to Workoflow Platform tools.

    This server provides access to tools configured in your Workoflow organization.

    IMPORTANT: You must have a valid X-Prompt-Token header configured in your MCP client.
    Get your token from your Workoflow profile page at /profile/.

    Available commands:
    1. workoflow_list_tools - List all available tools from your organization
    2. workoflow_execute - Execute any tool by name with parameters
    3. workoflow_refresh - Refresh the cached tool list

    Workflow:
    1. First call workoflow_list_tools to see available tools
    2. Use workoflow_execute with the tool name and required parameters
    """,
    lifespan=lifespan,
)


@mcp.tool
async def workoflow_list_tools() -> str:
    """List all available tools from your Workoflow organization.

    Returns a JSON list of tools with their names, descriptions, and parameters.
    Use this to discover what tools are available before calling workoflow_execute.

    Requires: X-Prompt-Token header in your MCP client configuration.
    """
    token = get_prompt_token()

    if not token:
        return json.dumps({
            "error": "No authentication token provided",
            "hint": "Add X-Prompt-Token header to your MCP client configuration. Get your token from /profile/ in Workoflow.",
        }, indent=2)

    cache = get_cache()
    client = get_client()

    # Check cache first
    cached_tools = cache.get(token, TOOL_TYPES)
    if cached_tools is not None:
        return json.dumps({
            "tools": _format_tools_for_display(cached_tools),
            "count": len(cached_tools),
            "cached": True,
        }, indent=2)

    try:
        tools = await client.fetch_tools(token, TOOL_TYPES or None)
        cache.set(token, TOOL_TYPES, tools)

        return json.dumps({
            "tools": _format_tools_for_display(tools),
            "count": len(tools),
            "cached": False,
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to fetch tools: {str(e)}",
            "hint": "Check if your token is valid and the Workoflow platform is reachable.",
        }, indent=2)


@mcp.tool
async def workoflow_execute(tool_name: str, parameters: str = "{}") -> str:
    """Execute a tool from your Workoflow organization.

    Args:
        tool_name: The name of the tool to execute (e.g., "jira_search_123", "system.searxng_tool").
                   Use workoflow_list_tools to see available tools.
        parameters: JSON string of parameters for the tool.
                    Example: '{"query": "search term", "limit": 10}'

    Returns:
        JSON result from the tool execution, or error details if failed.

    Requires: X-Prompt-Token header in your MCP client configuration.
    """
    token = get_prompt_token()

    if not token:
        return json.dumps({
            "error": "No authentication token provided",
            "hint": "Add X-Prompt-Token header to your MCP client configuration.",
        }, indent=2)

    # Parse parameters
    try:
        params = json.loads(parameters) if parameters else {}
    except json.JSONDecodeError as e:
        return json.dumps({
            "error": f"Invalid JSON parameters: {str(e)}",
            "hint": "Ensure parameters is a valid JSON string.",
        }, indent=2)

    client = get_client()

    try:
        result = await client.execute_tool(
            prompt_token=token,
            tool_id=tool_name,
            parameters=params,
        )

        if result.get("success"):
            return json.dumps(result.get("result", {}), indent=2, default=str)
        else:
            return json.dumps({
                "error": result.get("message", result.get("error", "Unknown error")),
                "hint": result.get("hint", "Check the error message for details."),
                "context": result.get("context", {}),
            }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"Tool execution failed: {str(e)}",
            "hint": "Check if the tool name is correct and parameters are valid.",
        }, indent=2)


@mcp.tool
async def workoflow_refresh() -> str:
    """Refresh the cached tool list from your Workoflow organization.

    Call this after adding/removing integrations in Workoflow to update the available tools.

    Returns:
        Confirmation message with the number of tools now available.

    Requires: X-Prompt-Token header in your MCP client configuration.
    """
    token = get_prompt_token()

    if not token:
        return json.dumps({
            "error": "No authentication token provided",
            "hint": "Add X-Prompt-Token header to your MCP client configuration.",
        }, indent=2)

    cache = get_cache()
    client = get_client()

    # Clear cache for this token
    cache.invalidate(token)

    try:
        tools = await client.fetch_tools(token, TOOL_TYPES or None)
        cache.set(token, TOOL_TYPES, tools)

        return json.dumps({
            "message": "Tool cache refreshed successfully",
            "tools_count": len(tools),
            "tools": [_get_tool_summary(t) for t in tools],
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to refresh tools: {str(e)}",
            "hint": "Check if your token is valid and the Workoflow platform is reachable.",
        }, indent=2)


def _format_tools_for_display(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format tools for display in list_tools response."""
    formatted = []
    for tool in tools:
        func = tool.get("function", tool)
        formatted.append({
            "name": func.get("name", "unknown"),
            "description": func.get("description", "No description"),
            "parameters": _summarize_parameters(func.get("parameters", {})),
        })
    return formatted


def _get_tool_summary(tool: dict[str, Any]) -> str:
    """Get a brief summary of a tool."""
    func = tool.get("function", tool)
    return func.get("name", "unknown")


def _summarize_parameters(schema: dict[str, Any]) -> dict[str, str]:
    """Summarize parameter schema for display."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    summary = {}
    for name, prop in properties.items():
        prop_type = prop.get("type", "any")
        prop_desc = prop.get("description", "")
        is_required = name in required

        summary[name] = f"{prop_type}{'*' if is_required else ''}: {prop_desc[:50]}..." if len(prop_desc) > 50 else f"{prop_type}{'*' if is_required else ''}: {prop_desc}"

    return summary


# Entry point for running with fastmcp CLI
if __name__ == "__main__":
    import sys

    # Print usage info
    print("Workoflow MCP Server")
    print("====================")
    print()
    print("Run with: fastmcp run workoflow_mcp.server:mcp --transport http --port 9000")
    print()
    print("Or use the Dockerfile for production deployment.")
