"""Use idpflow-core's MCP tools inside a CrewAI crew.

    pip install idpflow-core crewai 'crewai-tools[mcp]'
    export OPENAI_API_KEY=...           # for the agent LLM
    export VISION_AGENT_API_KEY=...     # optional; omit for stub mode
    python examples/make_sample_docs.py
    python examples/crewai_crew.py
"""

import glob
import os
from pathlib import Path

from crewai import Agent, Crew, Task
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

DOCS = sorted(glob.glob(str(Path(__file__).parent / "sample_docs" / "LN-DEMO-1" / "*.pdf")))

# Local stdio. Remote alternative:
#   server_params = {"url": "https://your-host/mcp", "transport": "streamable-http",
#                    "headers": {"Authorization": "Bearer <token>"}}
server_params = StdioServerParameters(
    command="idpflow-core", args=[], env=dict(os.environ)
)


def main() -> None:
    with MCPServerAdapter(server_params) as mcp_tools:
        processor = Agent(
            role="Loan document processor",
            goal="Extract and stack loan documents into a reviewable package",
            backstory="Operates idpflow-core to produce decision-ready document packages.",
            tools=mcp_tools,
            verbose=True,
        )
        task = Task(
            description=(
                "Process these documents as a mortgage package, then summarize the extracted "
                f"fields, the stack order, and any missing documents: {', '.join(DOCS)}"
            ),
            agent=processor,
            expected_output="A summary of extracted fields, the stack order, and any gaps.",
        )
        result = Crew(agents=[processor], tasks=[task]).kickoff()
        print(result)


if __name__ == "__main__":
    main()
