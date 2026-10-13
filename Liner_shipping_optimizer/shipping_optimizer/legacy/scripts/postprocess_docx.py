#!/usr/bin/env python3
"""
DOCX Post-Processor — Final polish for publication-quality output.

Handles:
  - Professional headers and footers with document title and version
  - Page numbering (Page X of Y)
  - Standardized figure layout
  - Internal hyperlinks (where supported)

Requires: python-docx (pip install python-docx)
"""

import sys
import os
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from docx.shared import RGBColor, Pt


DOCUMENTS = {
    "MASTER_TECHNICAL_DOCUMENTATION_V2.docx": {
        "title": "Master Technical Documentation V2",
        "subtitle": "AI Vessel Routing System",
        "version": "v1.0.0-rc1",
    },
    "ARCHITECTURE_REFERENCE.docx": {
        "title": "Architecture Reference",
        "subtitle": "AI Vessel Routing System",
        "version": "v1.0.0-rc1",
    },
    "CODE_REFERENCE.docx": {
        "title": "Code Reference",
        "subtitle": "AI Vessel Routing System",
        "version": "v1.0.0-rc1",
    },
}


def set_header_footer(doc, doc_info):
    """Set professional headers and footers for all sections."""
    project_name = "AI Vessel Routing System"
    doc_title = doc_info["title"]
    version = doc_info["version"]

    for section in doc.sections:
        # ── Header ──
        header = section.header
        # Clear existing header
        for p in header.paragraphs:
            p.clear()

        # Create header paragraph with two text runs
        if header.paragraphs:
            hp = header.paragraphs[0]
        else:
            hp = header.add_paragraph()

        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Left side: Project name
        run1 = hp.add_run(f"{project_name}")
        run1.font.size = 9 * 12700  # 9pt
        run1.font.name = "Arial"
        run1.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # Right side: Document title + version (tab separator)
        run2 = hp.add_run(f"\t| {doc_title}")
        run2.font.size = 9 * 12700
        run2.font.name = "Arial"
        run2.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        # Add a bottom border to header
        pPr = hp._p.get_or_add_pPr()
        pBdr = parse_xml(
            '<w:pBdr %s>'
            '  <w:bottom w:val="single" w:sz="4" w:space="1" w:color="999999"/>'
            '</w:pBdr>' % nsdecls('w')
        )
        pPr.append(pBdr)

        # ── Footer with page numbers ──
        footer = section.footer
        for p in footer.paragraphs:
            p.clear()

        if footer.paragraphs:
            fp = footer.paragraphs[0]
        else:
            fp = footer.add_paragraph()

        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Page X of Y using Word fields
        run_v = fp.add_run(f"{version}  |  ")
        run_v.font.size = 8 * 12700
        run_v.font.name = "Arial"
        run_v.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # "Page " text
        run_page = fp.add_run("Page ")
        run_page.font.size = 8 * 12700
        run_page.font.name = "Arial"
        run_page.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # PAGE field
        fld_char_begin = parse_xml('<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
        instr_text = parse_xml('<w:instrText %s xml:space="preserve"> PAGE </w:instrText>' % nsdecls('w'))
        fld_char_separate = parse_xml('<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
        fld_char_end = parse_xml('<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))

        run_fld = fp.add_run()
        run_fld._r.append(fld_char_begin)
        run_fld._r.append(instr_text)
        run_fld._r.append(fld_char_separate)
        run_fld._r.append(fld_char_end)

        # " of " text
        run_of = fp.add_run(" of ")
        run_of.font.size = 8 * 12700
        run_of.font.name = "Arial"
        run_of.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

        # NUMPAGES field
        fld_char_begin2 = parse_xml('<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
        instr_text2 = parse_xml('<w:instrText %s xml:space="preserve"> NUMPAGES </w:instrText>' % nsdecls('w'))
        fld_char_separate2 = parse_xml('<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
        fld_char_end2 = parse_xml('<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))

        run_fld2 = fp.add_run()
        run_fld2._r.append(fld_char_begin2)
        run_fld2._r.append(instr_text2)
        run_fld2._r.append(fld_char_separate2)
        run_fld2._r.append(fld_char_end2)

        # Add a top border to footer
        pPr_f = fp._p.get_or_add_pPr()
        pBdr_f = parse_xml(
            '<w:pBdr %s>'
            '  <w:top w:val="single" w:sz="4" w:space="1" w:color="999999"/>'
            '</w:pBdr>' % nsdecls('w')
        )
        pPr_f.append(pBdr_f)

    print(f"  Headers/footers updated: {doc_info['title']}")


def set_image_display(doc):
    """Ensure all images are centered and properly formatted."""
    for para in doc.paragraphs:
        # Check if paragraph contains an image
        for run in para.runs:
            drawing_elements = run._r.findall(qn('w:drawing'))
            if drawing_elements:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                break

    print("  Image centering applied")


def process_docx(input_path, doc_info):
    """Process a single DOCX file with all improvements."""
    print(f"\nProcessing: {os.path.basename(input_path)}")

    doc = Document(input_path)

    # Set headers and footers
    set_header_footer(doc, doc_info)

    # Center images
    set_image_display(doc)

    # Save
    doc.save(input_path)
    print(f"  Saved: {os.path.basename(input_path)} ({os.path.getsize(input_path) // 1024} KB)")
    return True


def main():
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "docs" / "generated"

    print("=" * 60)
    print("DOCX Post-Processor — Final Publication Polish")
    print("=" * 60)

    success = 0
    for filename, info in DOCUMENTS.items():
        docx_path = output_dir / filename
        if not docx_path.exists():
            print(f"  SKIP: {filename} not found")
            continue
        if process_docx(docx_path, info):
            success += 1

    print(f"\n{'=' * 60}")
    print(f"Processed {success}/{len(DOCUMENTS)} documents")
    print(f"{'=' * 60}")
    return 0 if success == len(DOCUMENTS) else 1


if __name__ == "__main__":
    sys.exit(main())
