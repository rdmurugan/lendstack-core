"""Use idpflow-core directly (no orchestrator). The simplest way in.

    python examples/make_sample_docs.py
    python examples/direct_library.py

Runs in STUB mode without VISION_AGENT_API_KEY (synthetic data, no API cost).
"""

import glob
from pathlib import Path

from idpflow_core.models import DocInput
from idpflow_core.package import build_package
from idpflow_core.render import render_package

DOCS = sorted(glob.glob(str(Path(__file__).parent / "sample_docs" / "LN-DEMO-1" / "*.pdf")))


def main() -> None:
    if not DOCS:
        raise SystemExit("No sample docs. Run: python examples/make_sample_docs.py")

    pkg = build_package("LN-DEMO-1", [DocInput(file_path=p) for p in DOCS], profile="mortgage")
    print(pkg.summary)
    print("\nStack order:")
    for it in pkg.ordered_stack:
        print(f"  {it.position}. {it.doc_type.value}  <- {Path(it.file_path).name}")
    print("\nExtracted fields:")
    for k in pkg.key_fields:
        flag = "  [REVIEW]" if k.needs_review else ""
        print(f"  [{k.source_doc.value}] {k.name} = {k.value}  (conf {k.confidence}, p{k.page}){flag}")

    rendered = render_package(pkg, output_dir=str(Path(__file__).parent / "out"))
    print(f"\nRendered package: {rendered.pdf_path} ({rendered.page_count} pages)")


if __name__ == "__main__":
    main()
