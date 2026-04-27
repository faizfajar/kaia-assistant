import asyncio
import logging
from typing import List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool
from pydantic import create_model


class MCPToolAdapter:
    """
    Adapter that converts MCP server tools into LangChain-compatible StructuredTools.

    Handles the async-to-sync bridge required by LangGraph's synchronous .invoke().
    Uses a closure factory to correctly capture tool names in the wrapper functions.
    """

    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params

    async def _call_tool(self, tool_name: str, args: dict) -> str:
        """
        Execute a single MCP tool call asynchronously.
        Opens a fresh stdio connection per call for isolation.
        """
        # Clean up None values so the MCP server can use its own defaults
        clean_args = {k: v for k, v in args.items() if v is not None}
        
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=clean_args)

                if not result.content:
                    return "Tool returned no output."

                return result.content[0].text

    def _make_sync_wrapper(self, tool_name: str):
        """
        Factory that creates a sync wrapper for a given MCP tool name.

        Safely handles the asyncio.run() vs running event loop conflict
        by detecting existing loops and using thread executors as fallback.
        """
        adapter = self

        def sync_wrapper(**kwargs) -> str:
            try:
                # Standard case — no existing event loop
                return asyncio.run(adapter._call_tool(tool_name, kwargs))
            except RuntimeError:
                # Fallback — already inside a running event loop (e.g. Jupyter)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        adapter._call_tool(tool_name, kwargs)
                    )
                    return future.result(timeout=30)

        return sync_wrapper

    async def get_tools(self) -> List[StructuredTool]:
        """
        Fetch all tools from the MCP server and convert them to LangChain StructuredTools.
        Returns empty list on failure to allow graceful degradation.
        """
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    mcp_tools = await session.list_tools()

                    langchain_tools = []
                    for t in mcp_tools.tools:
                      
                        props = t.inputSchema.get("properties", {})
                        required = t.inputSchema.get("required", [])
                        
                        fields = {}
                        for name, info in props.items():
                            fields[name] = (str, ... if name in required else None)
                          
                        ArgsSchema = create_model(f"{t.name}Schema", **fields)

                        langchain_tools.append(
                            StructuredTool.from_function(
                                func=self._make_sync_wrapper(t.name),
                                name=t.name,
                                description=t.description or f"MCP tool: {t.name}",
                                args_schema=ArgsSchema,
                            )
                        )

                    logging.info(
                        f"MCPToolAdapter: loaded {len(langchain_tools)} tools "
                        f"from {self.server_params.args}"
                    )
                    return langchain_tools

        except Exception as e:
            logging.error(f"MCPToolAdapter.get_tools() failed: {e}")
            return []