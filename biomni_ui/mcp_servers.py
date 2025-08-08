from pydantic_ai.mcp import MCPServerStreamableHTTP 

from biomni_ui.constants import _SERVER_PORTS

class MCPServerStreamableHTTPRestrictiveContext(MCPServerStreamableHTTP):
    def __init__(self, allowed_resources: list[str] | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_resources = allowed_resources or []

    async def list_tools(self):  # type: ignore[override]
        server_tools = await super().list_tools()
        if not self.allowed_resources:
            return server_tools
        return [t for t in server_tools if t.name in self.allowed_resources]

_SERVER_MAP: dict[str, MCPServerStreamableHTTPRestrictiveContext] = {
    name: MCPServerStreamableHTTPRestrictiveContext(url=f"http://0.0.0.0:{port}/mcp/")
    for name, port in _SERVER_PORTS.items()
}