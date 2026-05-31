# Examples

Runnable examples for each integration. All work in **stub mode** (no `VISION_AGENT_API_KEY`)
so you can try them free; set the key for live extraction.

```bash
pip install -e .                       # or: pip install idpflow-core
python examples/make_sample_docs.py    # writes a synthetic loan package
```

| File | What it shows | Extra deps |
|---|---|---|
| `direct_library.py` | Use the library directly — pipeline + render | none |
| `mcp_stdio_client.py` | Drive the MCP server over stdio (what Claude does) | none (uses bundled `mcp`) |
| `langgraph_agent.py` | MCP tools inside a LangGraph agent | `langchain-mcp-adapters langgraph langchain-openai` + `OPENAI_API_KEY` |
| `crewai_crew.py` | MCP tools inside a CrewAI crew | `crewai 'crewai-tools[mcp]'` + `OPENAI_API_KEY` |
| `claude_desktop_config.json` | Drop into Claude Desktop's config | Claude Desktop |

Run the no-extra-deps ones first:

```bash
python examples/direct_library.py
python examples/mcp_stdio_client.py
```

For Databricks, see [`../databricks/`](../databricks/). For the full per-platform guide, see
[`../docs/INTEGRATIONS.md`](../docs/INTEGRATIONS.md).
