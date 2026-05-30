"""Render a DocumentPackage into a combined, reviewable artifact.

Output = a single combined PDF (a cover sheet, then the source documents in stack order)
plus a JSON sidecar. The cover sheet ties every extracted field to its source document +
page so a reviewer can stare-and-compare, and surfaces the review queue and missing docs.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pypdf import PdfWriter

from .models import DocumentPackage, RenderedPackage

_INK = (17, 24, 39)
_MUTE = (107, 114, 128)
_FLAG = (185, 28, 28)
_OK = (21, 128, 61)

# Core PDF fonts are latin-1 only; map common unicode to ASCII so any extracted value renders.
_UNI = {
    "—": "-", "–": "-", "’": "'", "‘": "'",
    "“": '"', "”": '"', "→": "->", "•": "-", "…": "...",
    " ": " ",
}


def _s(text: str) -> str:
    text = str(text)
    for k, v in _UNI.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Cover(FPDF):
    def normalize_text(self, text):  # sanitize ALL text (header, cells, multi_cell) in one place
        return super().normalize_text(_s(text))

    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*_MUTE)
        self.cell(0, 6, "DOCUMENT PACKAGE — prepared for human review",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*_MUTE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_MUTE)
        self.cell(0, 6, f"Every value is grounded to a source page. Page {self.page_no()}",
                  align="C")


def _section(pdf: _Cover, title: str) -> None:
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _para(pdf: _Cover, text: str, h: float = 5.0) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, h, text)


def _render_cover(package: DocumentPackage, path: Path) -> None:
    pdf = _Cover()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 9, f"Package {package.package_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_MUTE)
    status = "COMPLETE" if package.is_complete else "INCOMPLETE"
    pdf.cell(0, 6, f"Stack: {package.profile}  |  File: {status}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_INK)
    _para(pdf, package.summary)

    # Missing docs
    if package.missing_docs:
        _section(pdf, "Missing required documents")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_FLAG)
        for m in package.missing_docs:
            pdf.cell(0, 5, f"  - {m.doc_type.value}: {m.reason}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)

    # Document stack
    _section(pdf, "Document stack (review order)")
    pdf.set_font("Helvetica", "", 9)
    for it in package.ordered_stack:
        flag = "  [REVIEW]" if it.review_required else ""
        conf = f"{it.overall_confidence:.2f}" if it.overall_confidence is not None else "-"
        line = f"  {it.position}. {it.doc_type.value}   (conf {conf}){flag}   <- {Path(it.file_path).name}"
        pdf.set_text_color(*( _FLAG if it.review_required else _INK))
        pdf.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)

    # Review queue
    if package.review_queue:
        _section(pdf, f"Review queue — {len(package.review_queue)} field(s) need human verification")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_FLAG)
        for k in package.review_queue:
            pdf.cell(0, 5, f"  - [{k.source_doc.value}] {k.name} = {k.value!r} (ungrounded/low-confidence)",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)

    # Extracted fields table
    _section(pdf, "Extracted fields (value -> source)")
    pdf.set_font("Helvetica", "B", 8)
    headers = [("Source", 32), ("Field", 62), ("Value", 50), ("Conf", 16), ("Pg", 10), ("OK", 12)]
    for label, w in headers:
        pdf.cell(w, 6, label, border="B")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for k in package.key_fields:
        pdf.set_text_color(*(_FLAG if k.needs_review else _INK))
        conf = f"{k.confidence:.2f}" if k.confidence is not None else "-"
        ok = "!" if k.needs_review else "ok"
        cells = [
            (k.source_doc.value, 32),
            ((k.name or "")[:40], 62),
            ((str(k.value) if k.value is not None else "-")[:30], 50),
            (conf, 16),
            (str(k.page or "-"), 10),
            (ok, 12),
        ]
        for text, w in cells:
            pdf.cell(w, 5, text, border="B")
        pdf.ln()
    pdf.set_text_color(*_INK)

    pdf.output(str(path))


def render_package(
    package: DocumentPackage, output_dir: str = "./out"
) -> RenderedPackage:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in package.package_id)
    cover_path = out / f"{safe_id}_cover.pdf"
    pdf_path = out / f"{safe_id}_package.pdf"
    json_path = out / f"{safe_id}_package.json"

    _render_cover(package, cover_path)

    writer = PdfWriter()
    writer.append(str(cover_path))
    embedded = 0
    not_embedded: list[str] = []
    for item in package.ordered_stack:
        fp = item.file_path
        if fp.lower().endswith(".pdf") and Path(fp).exists():
            try:
                writer.append(fp)
                embedded += 1
            except Exception:  # noqa: BLE001
                not_embedded.append(Path(fp).name)
        else:
            not_embedded.append(Path(fp).name)
    with open(pdf_path, "wb") as fh:
        writer.write(fh)
    page_count = len(writer.pages)
    writer.close()
    cover_path.unlink(missing_ok=True)

    json_path.write_text(package.model_dump_json(indent=2))

    return RenderedPackage(
        package_id=package.package_id,
        pdf_path=str(pdf_path),
        json_path=str(json_path),
        page_count=page_count,
        docs_embedded=embedded,
        docs_not_embedded=not_embedded,
        package=package,
    )
