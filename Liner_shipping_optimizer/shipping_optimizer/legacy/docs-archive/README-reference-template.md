# Using `reference.docx`

## Basic conversion

```bash
pandoc MASTER_TECHNICAL_DOCUMENTATION.md \
  --reference-doc=reference.docx \
  --toc --toc-depth=3 \
  --number-sections \
  --highlight-style=tango \
  -o output.docx
```

## What's built in

- **Page setup**: A4, 2.54 cm margins (3 cm left for binding), 0.5 cm gutter, header/footer 1.25 cm from edge, different first page (cover page gets no header/footer).
- **Fonts**: Calibri Light (headings) / Calibri (body) / Consolas (code), wired through the theme so `majorHAnsi`/`minorHAnsi` resolve correctly.
- **Colors**: deep blue `#1F4E79` (H1/H2, links, table headers), slate `#44546A` (H3–H6, captions), plus the full callout palette from the spec.
- **Header/footer**: pre-filled with `Project Name` / `Document Title` placeholders and `Draft · v0.1 · Page X of Y` — edit the text directly in `word/header1.xml` / `word/footer1.xml` (or in Word itself, under Insert > Header) before use on a real project.
- **All 30 Pandoc-mapped styles** from the specification (`Normal`, `Title`, `Subtitle`, `Heading 1`–`6`, `Source Code`, `Block Text`, `Caption`/`Table Caption`/`Image Caption`, `TOC 1`–`3`, `Header`, `Footer`, `Table`, `Hyperlink`, `First Paragraph`, `Compact`, plus `Appendix Heading`).
- **Callout boxes** (`Note Box`, `Tip Box`, `Important Box`, `Warning Box`, `Definition Box`, `Example Box`) — not auto-triggered by plain Markdown, but usable via a fenced div:

  ```markdown
  ::: {custom-style="Warning Box"}
  **Warning.** Don't run this in production without a backup.
  :::
  ```

## Not included (by design)

Per the original brief, this file has **no project content**. A few pieces from the spec are *authoring-time* decisions rather than template styling, so they aren't baked in:

- Cover page field values, revision history rows, TOC/List of Figures/List of Tables content — these come from the Markdown/YAML front matter and Pandoc's `--toc` flag at conversion time, not from the reference doc.
- Mermaid diagrams must be pre-rendered to PNG/SVG before the Pandoc pass (§13 of the spec).
- The Index (§27) is a manual post-processing step — omit it unless you're producing the thesis-report variant.

## Verifying after edits

```bash
pandoc sample.md --reference-doc=reference.docx --toc -o out.docx
soffice --headless --convert-to pdf out.docx
pdftoppm -jpeg -r 100 out.pdf page   # then look at page-*.jpg
```

See `REFERENCE_TEMPLATE_DESIGN_SPECIFICATION.md` for the full design rationale behind every value used here.
