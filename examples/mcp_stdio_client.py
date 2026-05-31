"""Drive idpflow-core as an MCP server over stdio, using the MCP client SDK.

This is what Claude / any MCP client does under the hood.

    pip install idpflow-core            # provides the `idpflow-core` command
    python examples/make_sample_docs.py
    python examples/mcp_stdio_client.py

Runs in STUB mode without VISION_AGENT_API_KEY.
"""

import asyncio
import glob
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DOCS = sorted(glob.glob(str(Path(__file__).parent / "sample_docs" / "LN-DEMO-1" / "*.pdf")))

# Launch the installed console script. (Alternatively: command=sys.executable,
# args=["-m", "idpflow_core.server"] if running from a source checkout.)
SERVER = StdioServerParameters(command="idpflow-core", args=[], env=dict(os.environ))


async def main() -> None:
    if not DOCS:
        raise SystemExit("No sample docs. Run: python examples/make_sample_docs.py")

    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            result = await session.call_tool(
                "process_documents",
                {
                    "package_id": "LN-DEMO-1",
                    "documents": [{"file_path": p} for p in DOCS],
                    "profile": "mortgage",
                },
            )
            # Structured result is in result.structuredContent (or .content text).
            print("\nResult:")
            print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
