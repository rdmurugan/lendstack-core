"""idpflow-core — agentic document extraction + stacking over LandingAI ADE, as an MCP server.

Transport:
  - stdio (default): local dev / Claude Desktop.
  - streamable-http: remote server (OAuth 2.1 required) for Claude / Connectors Directory.

What it does: ingest documents from any source, classify them, extract typed fields with
confidence + page/bbox provenance (ADE grounding), stack them in a configurable order, and
render a combined review package (PDF + JSON). It surfaces grounded data for a human to act
on — it does not make decisions.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import stacking as S
from .auth import build_auth
from .ade_client import ADEClient
from .classify import classify_document
from .package import build_package
from .render import render_package
from .models import (
    ClassifyResult,
    DocInput,
    DocType,
    DocumentExtraction,
    DocumentPackage,
    RenderedPackage,
    StackResult,
)

load_dotenv()

# OAuth Resource-Server auth (from env). (None, None) => unauthenticated (local stdio dev).
_token_verifier, _auth_settings = build_auth()

mcp = FastMCP(
    "idpflow-core",
    instructions=(
        "Document extraction + stacking over LandingAI ADE. Extract typed fields with "
        "confidence + page-level provenance, classify documents, stack them in a configurable "
        "order, and render a combined review package. Surfaces grounded data for a human to "
        "act on; it does not make decisions."
    ),
    token_verifier=_token_verifier,
    auth=_auth_settings,
)

_ade = ADEClient()


@mcp.tool(
    annotations={"title": "Extract document", "readOnlyHint": True, "openWorldHint": True}
)
def extract_document(file_path: str, doc_type: str) -> DocumentExtraction:
    """Extract structured fields from a single document via LandingAI ADE.

    Returns each field with a confidence score and visual provenance (page + bounding box)
    so outputs are auditable. Fields below the confidence threshold are flagged needs_review.

    Args:
        file_path: Absolute path or URL to the document (PDF/image).
        doc_type: A known DocType value, or 'other'. Drives the extraction schema.
    """
    try:
        dt = DocType(doc_type)
    except ValueError:
        valid = ", ".join(d.value for d in DocType)
        raise ValueError(f"Unknown doc_type '{doc_type}'. Use one of: {valid}")
    return _ade.extract(file_path, dt)


@mcp.tool(annotations={"title": "Classify a document", "readOnlyHint": True})
def classify_document_tool(file_path: str, hint: str | None = None) -> ClassifyResult:
    """Determine a document's type (for stacking + schema selection).

    Uses an explicit hint if given, else ADE-parsed markdown keywords, else a filename
    heuristic. Works offline (filename) and live (markdown).
    """
    return classify_document(file_path, hint=hint, client=_ade)


@mcp.tool(annotations={"title": "Stack documents in order", "readOnlyHint": True})
def stack_documents(
    documents: list[DocInput], profile: str = "mortgage", custom_order: list[str] | None = None
) -> StackResult:
    """Order a set of documents into a configured stack.

    Document-source-agnostic: works on any list of docs regardless of how they arrived
    (upload portal, SFTP/S3, email, or export). Example profiles: mortgage | auto_indirect |
    auto_direct. Pass custom_order (list of doc_type values) to override the profile order.
    """
    if profile not in S.STACK_PROFILES and not custom_order:
        raise ValueError(f"Unknown profile '{profile}'. Profiles: {', '.join(S.profiles())}")
    present: list[tuple[DocType, str]] = []
    for d in documents:
        dt = DocType(d.doc_type) if d.doc_type else classify_document(
            d.file_path, client=_ade
        ).doc_type
        present.append((dt, d.file_path))
    order = [DocType(o) for o in custom_order] if custom_order else None
    return S.stack_documents(present, profile=profile, custom_order=order)


@mcp.tool(
    annotations={"title": "Process documents", "readOnlyHint": True, "openWorldHint": True}
)
def process_documents(
    package_id: str, documents: list[DocInput], profile: str = "mortgage"
) -> DocumentPackage:
    """End-to-end pipeline: ingest → classify → extract → stack → assemble.

    Returns a DocumentPackage: documents stacked in the configured order, every field carried
    with confidence + page provenance, and a review queue of ungrounded / low-confidence
    values. Source-agnostic. Carries no decision.

    Args:
        package_id: Your identifier for this set of documents.
        documents: Docs to process (file_path + optional doc_type).
        profile: stack profile (e.g. mortgage | auto_indirect | auto_direct).
    """
    return build_package(package_id, documents, profile=profile, client=_ade)


@mcp.tool(
    annotations={"title": "Render document package (PDF + JSON)", "openWorldHint": True}
)
def render_document_package(
    package_id: str,
    documents: list[DocInput],
    profile: str = "mortgage",
    output_dir: str = "./out",
) -> RenderedPackage:
    """Produce a combined review artifact: a cover sheet + source docs merged in stack order,
    plus a JSON sidecar.

    Runs the full pipeline, then renders a cover sheet (extracted fields tied to source page,
    review queue, missing docs) followed by the source documents merged in stack order.

    Args:
        package_id: Identifier for this set of documents.
        documents: Docs to process (file_path + optional doc_type).
        profile: stack profile.
        output_dir: Directory to write the PDF + JSON into.
    """
    package = build_package(package_id, documents, profile=profile, client=_ade)
    return render_package(package, output_dir=output_dir)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "streamable-http":
        # Remote mode — OAuth required.
        if _token_verifier is None and os.getenv("MCP_ALLOW_INSECURE") != "1":
            raise SystemExit(
                "Refusing to start a remote (streamable-http) server without OAuth. "
                "Configure OAUTH_ISSUER + OAUTH_AUDIENCE + MCP_RESOURCE_URL (production) "
                "or MCP_DEV_BEARER_TOKEN + MCP_RESOURCE_URL (dev). "
                "Set MCP_ALLOW_INSECURE=1 only behind your own trusted gateway."
            )
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8080"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()  # stdio (local dev; unauthenticated by design)


if __name__ == "__main__":
    main()
