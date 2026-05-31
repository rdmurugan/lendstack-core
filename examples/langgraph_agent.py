"""Use idpflow-core's MCP tools inside a LangGraph agent.

    pip install idpflow-core langchain-mcp-adapters langgraph langchain-openai
    export OPENAI_API_KEY=...           # for the agent LLM
    export VISION_AGENT_API_KEY=...     # optional; omit for stub mode
    python examples/make_sample_docs.py
    python examples/langgraph_agent.py
"""

import asyncio
import glob
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

DOCS = sorted(glob.glob(str(Path(__file__).parent / "sample_docs" / "LN-DEMO-1" / "*.pdf")))


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "idpflow": {
                "transport": "stdio",
                "command": "idpflow-core",
                "args": [],
                # Remote instead:
                # "transport": "streamable_http",
                # "url": "https://your-host/mcp",
            }
        }
    )
    tools = await client.get_tools()
    agent = create_react_agent("openai:gpt-4o", tools)

    files = ", ".join(DOCS)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Process these documents as a mortgage package and summarize the "
                        f"extracted fields, the stack order, and any missing documents: {files}"
                    ),
                }
            ]
        }
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
