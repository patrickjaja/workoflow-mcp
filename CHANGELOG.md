# Changelog

All notable changes to this project will be documented in this file.

## 2026-01-15

### Fixed
- **FastMCP 2.x CLI compatibility** - Updated Dockerfile to use file path syntax (`src/workoflow_mcp/server.py:mcp`) instead of module path syntax which FastMCP 2.x no longer supports
- **Relative imports error** - Changed imports in server.py from relative (`from .cache`) to absolute (`from workoflow_mcp.cache`) to work with FastMCP's direct file execution
- **Docker container network access** - Added `--host 0.0.0.0` to allow connections from outside the container
- **Health check** - Changed from HTTP endpoint check to TCP socket check since FastMCP doesn't expose `/health`

### Changed
- **SSE transport** - Switched from `http` to `sse` transport for better compatibility with MCP clients like Claude Desktop via mcp-remote
- **Package installation** - Now uses `pip install .` with pyproject.toml instead of requirements.txt for proper package installation

## 2026-01-14

### Added
- **Initial release** - MCP Server Bridge for Workoflow Platform
- **Token-based authentication** - Uses personal access tokens from Workoflow profile (`X-Prompt-Token` header)
- **Tool discovery** - `workoflow_list_tools` command to list all available tools from your organization
- **Tool execution** - `workoflow_execute` command to run any Workoflow tool by name with parameters
- **Cache refresh** - `workoflow_refresh` command to refresh the cached tool list
- **TTL caching** - Configurable cache for tool definitions (default 10 minutes)
- **OpenTelemetry integration** - Phoenix tracing support for observability
- **Docker support** - Dockerfile and docker-compose integration for workoflow-ai-setup
- **Streamable HTTP transport** - Modern MCP transport protocol for Claude Code, Cursor, and other AI tools
