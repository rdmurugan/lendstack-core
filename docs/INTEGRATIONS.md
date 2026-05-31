# Using lendstack-core with Claude, Databricks, Lyzr, LangGraph, and CrewAI

`lendstack-core` ships as an **MCP server** with 5 tools, plus a **Databricks batch job**. Any
MCP-speaking orchestrator can drive it. This guide shows each.

## The 5 tools (same everywhere)

| Tool | Does |
|---|---|
| `extract_document(file_path, doc_type)` | ADE-extract one doc → fields + confidence + page/bbox |
| `classify_document(file_path, hint?)` | Detect a document's type |
| `stack_documents(documents, profile?, custom_order?)` | Order a set of docs into a stack |
| `process_documents(package_id, documents, profile?)` | Ingest → classify → extract → stack |
| `render_document_package(package_id, documents, profile?, output_dir?)` | Combined PDF + JSON |

## Prerequisites

```bash
pip install git+https://github.com/rdmurugan/lendstack-core.git
export VISION_AGENT_API_KEY=...   # your LandingAI key; omit for STUB mode (synthetic, free)
```

**Two ways to run the server:**
- **stdio** (local): the `lendstack-core` command. Best for desktop apps and local agents.
- **streamable-http** (remote): set `MCP_TRANSPORT=streamable-http` + OAuth env (see
  [`DEPLOY.md`](DEPLOY.md)). Best for hosted orchestrators. Reachable at `http://<host>:8080/mcp`.

---

## 1. Claude

### Claude Desktop (local, stdio)
Edit `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "lendstack": {
      "command": "lendstack-core",
      "env": { "VISION_AGENT_API_KEY": "your-key" }
    }
  }
}
```

Restart Claude Desktop. The 5 tools appear; ask e.g. *"Process the loan docs in /path/to/file
and stack them as mortgage."* Claude calls `process_documents` and reasons over the result.

### Claude (web / Connectors Directory, remote)
Run the server in **streamable-http** mode behind OAuth (`DEPLOY.md`), then add it as a **custom
connector** (Settings → Connectors → Add custom connector → your `https://.../mcp` URL). Remote
mode requires OAuth 2.1 — the server refuses to start without it.

---

## 2. Databricks (batch / lakehouse)

Not MCP — the library runs directly in a notebook/job. Documents in a Unity Catalog Volume →
classify / extract / stack → Delta tables. See [`../databricks/`](../databricks/):

```python
%pip install git+https://github.com/rdmurugan/lendstack-core.git
# set VISION_AGENT_API_KEY from a Databricks secret, point at a Volume, run -> Delta tables
```

Full setup in [`databricks/README.md`](../databricks/README.md). Runs inside the customer's
workspace, so PII never leaves their boundary.

---

## 3. Lyzr AI (Agent Studio)

Lyzr speaks MCP natively. Run the server in **streamable-http** mode, then in **Agent Studio →
Add Server** enter the MCP endpoint URL (`https://.../mcp`) and its auth. Once added, any agent in
Studio can call the 5 tools — no custom code. Publish the resulting agent to the Lyzr Marketplace
if you want it discoverable.

---

## 4. LangGraph (langchain-mcp-adapters)

```bash
pip install langchain-mcp-adapters langgraph langchain-openai
```

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

async def main():
    client = MultiServerMCPClient({
        "lendstack": {
            # local stdio:
            "transport": "stdio",
            "command": "lendstack-core",
            "args": [],
            # or remote:
            # "transport": "streamable_http",
            # "url": "https://your-host/mcp",
        }
    })
    tools = await client.get_tools()
    agent = create_react_agent("openai:gpt-4o", tools)
    res = await agent.ainvoke({"messages": [
        {"role": "user",
         "content": "Process the docs in /data/LN-1 and stack them as mortgage; list any missing docs."}
    ]})
    print(res["messages"][-1].content)

asyncio.run(main())
```

For remote mode, pass the bearer token via the client config's transport headers.
Docs: [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters).

---

## 5. CrewAI (crewai-tools)

```bash
pip install crewai 'crewai-tools[mcp]'
```

```python
import os
from crewai import Agent, Task, Crew
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

# Local stdio:
server_params = StdioServerParameters(
    command="lendstack-core",
    args=[],
    env={"VISION_AGENT_API_KEY": os.environ["VISION_AGENT_API_KEY"], **os.environ},
)
# Or remote streamable-http:
# server_params = {"url": "https://your-host/mcp", "transport": "streamable-http",
#                  "headers": {"Authorization": "Bearer <token>"}}

with MCPServerAdapter(server_params) as mcp_tools:
    processor = Agent(
        role="Loan document processor",
        goal="Extract and stack loan documents for an underwriter",
        backstory="Operates lendstack-core to produce decision-ready packages.",
        tools=mcp_tools,
    )
    task = Task(
        description="Process the docs in /data/LN-1, stack as mortgage, summarize fields + gaps.",
        agent=processor,
        expected_output="A summary of extracted fields, the stack order, and any missing docs.",
    )
    Crew(agents=[processor], tasks=[task]).kickoff()
```

Docs: [CrewAI MCP](https://docs.crewai.com/en/mcp/overview).

---

## Notes that apply to all integrations

- **Stub mode** — without `VISION_AGENT_API_KEY`, every tool returns synthetic data, so you can
  wire up any orchestrator before spending on ADE.
- **Provenance** — extracted values carry confidence + source page; ungrounded values are
  flagged `needs_review`. Surface that to your reviewer; don't auto-decide.
- **Remote = OAuth** — the streamable-http server won't start without OAuth 2.1 (or an explicit
  insecure override behind your own gateway).
