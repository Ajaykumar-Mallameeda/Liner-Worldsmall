# Reference Template Design Specification

**Document purpose:** This specification defines the complete visual and structural design of `reference.docx` — a style-only Word template used by Pandoc to render all project Markdown documentation (technical docs, architecture references, API references, guides, thesis reports) into professional, consistent Word/PDF output. It contains no project content. It is a permanent, reusable design standard.

**Status:** Design specification (not the template file itself)
**Target quality:** Enterprise engineering documentation / graduate thesis quality
**Primary consumer:** Pandoc (`pandoc input.md --reference-doc=reference.docx -o output.docx`)

---

## 1. Design Philosophy

The template borrows conventions from Microsoft Docs, AWS technical documentation, Google engineering style guides, NVIDIA developer docs, and formal thesis/OR (Operations Research) report formatting. Three principles govern every decision below:

1. **Restraint over decoration.** Structure is communicated through spacing, weight, and a small consistent color palette — not through boxes, gradients, or excessive rules.
2. **Scan-first reading.** Headings, captions, and callouts must be identifiable at a glance when a reader skims the document at 50% zoom.
3. **Print/PDF parity.** Every choice must survive black-and-white printing and PDF export without loss of meaning (see §28–29).

**Color palette (used sparingly — text stays near-black by default):**

| Role | Name | Hex | Use |
|---|---|---|---|
| Primary accent | Deep Blue | `#1F4E79` | H1/H2, links, table headers |
| Secondary accent | Slate | `#44546A` | H3–H6, captions |
| Success/Tip | Forest Green | `#2E7D32` | Tip callouts |
| Warning | Amber | `#B36B00` | Warning callouts |
| Critical | Deep Red | `#B00020` | Important/Critical callouts |
| Neutral fill | Light Gray | `#F2F2F2` | Table alt-rows, code background |
| Rule/border | Mid Gray | `#BFBFBF` | Table borders, horizontal rules |
| Body text | Near Black | `#1A1A1A` | Body copy |

All accent colors carry a contrast ratio ≥ 4.5:1 against white, satisfying WCAG AA (see §28).

---

## 2. Page Setup

| Property | Value |
|---|---|
| Paper size | A4 (210 × 297 mm) — see §29 for US Letter variant |
| Orientation | Portrait (default); Landscape section for wide tables (§6) |
| Top margin | 2.54 cm (1") |
| Bottom margin | 2.54 cm (1") |
| Left margin | 3.0 cm (allows binding) |
| Right margin | 2.54 cm |
| Gutter | 0.5 cm |
| Mirror margins | Enabled only if the document will be duplex-printed and bound (thesis/report use case); disabled for digital-only docs |
| Header distance from edge | 1.25 cm |
| Footer distance from edge | 1.25 cm |
| Section breaks | Next-page section break before each top-level (H1) chapter, so headers/footers and landscape pages can vary per chapter |

---

## 3. Typography

| Role | Font | Fallback |
|---|---|---|
| Primary (headings) | Calibri Light | Arial |
| Secondary (body) | Calibri | Arial |
| Monospace (code) | Consolas | Courier New |

| Style | Size | Weight | Line spacing |
|---|---|---|---|
| Body text | 11 pt | Regular | 1.15 (multiple) |
| Captions | 9.5 pt | Regular, italic | 1.0 |
| Code | 10 pt | Regular | 1.0 |
| Footnotes | 9 pt | Regular | 1.0 |

**Paragraph spacing:** 6 pt before, 8 pt after body paragraphs; 0 pt between consecutive list items.

**Additional rules:**
- Widow/orphan control: **on** for all body and list styles.
- Hyphenation: automatic, enabled document-wide, with a 2-character minimum before/after break.
- Kerning: on, ≥ 14 pt.
- Justification: body text left-aligned (not justified) to avoid uneven rag/rivers in a technical document; this also improves screen-reader and translation-tool compatibility.

---

## 4. Heading Hierarchy

All headings use Calibri Light, color-coded, with `keep with next` enabled so a heading never sits alone at the bottom of a page.

| Level | Size | Weight | Color | Space before / after | Page break | Outline level | TOC level |
|---|---|---|---|---|---|---|---|
| Title (cover only) | 28 pt | Bold | `#1F4E79` | — | — | 0 | — |
| H1 | 20 pt | Bold | `#1F4E79` | 24 pt / 12 pt | Starts new page (section break) | 1 | 1 |
| H2 | 16 pt | Bold | `#1F4E79` | 18 pt / 8 pt | No | 2 | 2 |
| H3 | 13 pt | Bold | `#44546A` | 14 pt / 6 pt | No | 3 | 3 |
| H4 | 12 pt | Bold, italic | `#44546A` | 12 pt / 4 pt | No | 4 | 4 |
| H5 | 11 pt | Bold | `#44546A` | 10 pt / 4 pt | No | 5 | Excluded (too granular) |
| H6 | 11 pt | Italic (no bold) | `#44546A` | 8 pt / 4 pt | No | 6 | Excluded |

A thin 0.5 pt `#BFBFBF` bottom border under H1 only, adding a clear chapter boundary without a full-width fill.

---

## 5. Normal Paragraph Style

| Property | Value |
|---|---|
| Alignment | Left |
| Line spacing | 1.15 |
| Space before / after | 6 pt / 8 pt |
| First-line indent | None (block style, spacing-separated — standard for technical docs) |
| Keep with next | Off (body doesn't need to stick to the next paragraph) |
| Keep lines together | On (a single paragraph should not split mid-sentence across a page boundary when avoidable) |
| Widow/orphan control | On |

---

## 6. Lists

| List type | Marker | Indent (per level) | Spacing |
|---|---|---|---|
| Bulleted (L1) | `●` solid round, `#1A1A1A` | 0.63 cm | 2 pt between items |
| Bulleted (L2) | `○` open round | 1.27 cm | 2 pt |
| Bulleted (L3) | `▪` small square | 1.90 cm | 2 pt |
| Numbered (L1) | `1. 2. 3.` Arabic | 0.63 cm | 2 pt |
| Numbered (L2) | `a. b. c.` lowercase alpha | 1.27 cm | 2 pt |
| Numbered (L3) | `i. ii. iii.` lowercase roman | 1.90 cm | 2 pt |
| Checklist | `☐` / `☑` (Wingdings 2 or Segoe UI Symbol) | 0.63 cm | 3 pt |

List paragraphs use the body font at 11 pt; nested lists never exceed 3 levels in project documentation (a 4th level should be refactored into a table or sub-heading).

---

## 7. Code Blocks

Applies to Python, JSON, YAML, Bash, and PowerShell fenced blocks alike — language-specific syntax coloring is a "nice-to-have" via Pandoc's `--highlight-style`, but the **box style itself is uniform**:

| Property | Value |
|---|---|
| Font | Consolas, 10 pt |
| Background shading | `#F2F2F2` (light gray, `ShadingType.CLEAR` if built programmatically) |
| Border | 0.75 pt solid `#BFBFBF`, all sides |
| Padding | 6 pt top/bottom, 8 pt left/right |
| Line spacing | 1.0 (single) |
| Page-split behavior | "Keep lines together" enabled on the paragraph so a short block never splits; long blocks (> ~40 lines) are allowed to split across pages with the border repeating (Word table-based code blocks with "repeat header row" are **not** used, since code has no header — a bordered paragraph frame is preferred) |
| Wrapping | No line wrap; rely on the block staying within the text width. Long lines should be pre-wrapped in the source Markdown at ~90 characters. |

**Pandoc mapping:** fenced code blocks map to Word style `Source Code` (aliased in the reference doc as **Code**, see §30). Pandoc's `--highlight-style=pygments` (or `tango`) is recommended for token coloring on top of this box.

---

## 8. Inline Code

Separate character style, distinct from block code:

| Property | Value |
|---|---|
| Font | Consolas, 10.5 pt (slightly smaller than surrounding 11 pt body optically balances monospace width) |
| Background shading | `#F2F2F2` |
| Border | None (background alone is sufficient at inline scale) |
| Color | `#1A1A1A` (no accent color — inline code should not compete with hyperlinks) |

---

## 9. Block Quotes

| Property | Value |
|---|---|
| Left border | 3 pt solid `#1F4E79` |
| Left indent | 0.5 cm |
| Font | Calibri, 11 pt, italic |
| Color | `#44546A` |
| Background | None (keeps quotes visually lighter than callouts, see §16) |
| Space before/after | 10 pt / 10 pt |

---

## 10. Hyperlinks

| Property | Value |
|---|---|
| Color | `#1F4E79` (matches primary accent, reinforcing brand consistency) |
| Underline | Single, on hover in digital readers; always-on underline in print styling since color alone isn't reliable in grayscale (see §29) |
| Visited state | Not distinguished (Word doesn't track this meaningfully in generated docs) |
| External link indicator | Optional small ↗ suffix character for links leaving the project domain (manual convention, not automatic) |

---

## 11. Captions

| Type | Format | Position |
|---|---|---|
| Figure | `Figure X.Y — Description` | Below the image |
| Table | `Table X.Y — Description` | Above the table |
| Equation | `(X.Y)` right-aligned | Same line as equation, right margin |
| Algorithm | `Algorithm X.Y — Description` | Above the algorithm block |

Where `X` = chapter (H1) number and `Y` = sequential counter within chapter, both driven by Word `SEQ` fields so renumbering is automatic when content is reordered.

**Caption style:** Calibri, 9.5 pt, italic, `#44546A`, centered for figures/algorithms, left-aligned for tables, 6 pt space before, 12 pt after.

---

## 12. Images

| Property | Value |
|---|---|
| Alignment | Centered |
| Maximum width | 15.5 cm (fits within the text column at the margins defined in §2) |
| Minimum margin around image | 0.5 cm clearance from surrounding text (achieved via paragraph spacing, not text-wrap-around — technical docs use in-line, not floating, images) |
| Caption placement | Directly below, no gap larger than 4 pt |
| Numbering | Sequential per chapter: `Figure 3.1`, `Figure 3.2`, via `SEQ Figure \* ARABIC` bookmarked to H1 |
| Resolution | Minimum 150 DPI at display size; 300 DPI preferred for print-quality PDF export |

---

## 13. Mermaid Diagrams

Pandoc cannot render Mermaid natively, so diagrams must be pre-rendered before the Markdown → Word pass.

| Recommendation | Value |
|---|---|
| Export format | **SVG** for the master asset (scales losslessly, small file size); rasterize to **PNG at 2× scale** at pipeline time for embedding, since Word's SVG support is inconsistent across versions |
| Recommended render width | 1600 px source width (renders crisp at the 15.5 cm max width from §12 even at 2× DPI) |
| Caption placement | Same as Figure captions (§11) — Mermaid diagrams are numbered as Figures, not a separate category |
| Page positioning | Keep-with-next on the diagram paragraph and keep-with-previous on its caption, so the pair never splits across a page break |
| Pipeline step | `mmdc -i diagram.mmd -o diagram.png -w 1600 -s 2 -b transparent` (or equivalent), then reference the PNG in Markdown as a normal image |

---

## 14. Equations

| Property | Value |
|---|---|
| Format | Word native equation objects (OMML) via Pandoc's LaTeX-math → OMML conversion (`--mathml` not needed for docx; Pandoc converts automatically) |
| Alignment | Centered, with the equation number right-aligned on the same line using a tab stop |
| Numbering | `(Chapter.Sequence)`, e.g., `(4.3)`, via `SEQ Equation` field |
| Spacing | 12 pt before/after, isolated in its own paragraph (never inline with body text for anything beyond a short inline expression) |
| Font | Cambria Math (Word's default equation font — do not override) |

---

## 15. Algorithms

| Property | Value |
|---|---|
| Font | Consolas, 10 pt (same family as code, to visually associate pseudo-code with code) |
| Background | White (not shaded, to distinguish from literal code blocks) |
| Border | Full 1 pt solid `#44546A` box, with a header band |
| Header band | `#1F4E79` fill, white text, containing `Algorithm X.Y: Title` |
| Line numbering | Left-aligned line numbers in a narrow gutter column, gray `#BFBFBF` |
| Numbering | Sequential per chapter, same `SEQ` mechanism as Figures/Tables |
| Indentation | 4-space-equivalent per nesting level (`for`, `if`, `while` blocks), rendered as a hanging indent |

---

## 16. Callout Boxes

Six semantic callout types, each a bordered box with a colored left bar, an icon-style label, and light tint fill (tints stay light enough to keep body text at full contrast — see §28):

| Type | Left bar / label color | Fill tint | Label |
|---|---|---|---|
| Note | `#44546A` | `#F2F3F5` | **Note** |
| Tip | `#2E7D32` | `#EAF5EA` | **Tip** |
| Important | `#B00020` | `#FBE9EB` | **Important** |
| Warning | `#B36B00` | `#FCF0DE` | **Warning** |
| Definition | `#1F4E79` | `#EAF0F6` | **Definition** |
| Example | `#5B3A8E` | `#F1EAF7` | **Example** |

Common structure: 4 pt left border in the role color, 8 pt padding all sides, 10 pt space before/after, bold role label on its own first line (11 pt, role color), body text below at standard 11 pt Calibri.

---

## 17. Header

| Zone | Content |
|---|---|
| Left | Project name (e.g., repository name), 9 pt, `#44546A` |
| Center | (blank — avoids visual clutter) |
| Right | Document title, 9 pt, `#44546A` |
| Bottom rule | 0.5 pt `#BFBFBF` line separating header from body |
| Optional | A `Confidential — Internal Use Only` tag, 8 pt, `#B00020`, centered, only inserted for documents explicitly marked confidential |
| First-page behavior | Suppressed on the cover page (different-first-page header) |

---

## 18. Footer

| Zone | Content |
|---|---|
| Left | Document status (e.g., `Draft`, `Final`, `Under Review`) — 9 pt, `#44546A` |
| Center | Version, e.g., `v1.3` — 9 pt |
| Right | `Page X of Y` via `PAGE`/`NUMPAGES` fields — 9 pt |
| Bottom rule | 0.5 pt `#BFBFBF` line separating footer from body |
| First-page behavior | Suppressed on cover page |

---

## 18a. Front Matter Pages (implied by §19–20, listed for completeness)

Front matter (cover, revision history, TOC, list of figures/tables) uses lowercase Roman page numbering (`i, ii, iii…`); the main body restarts at Arabic `1` from the first H1 chapter, via a section break with "restart numbering."

---

## 19. Cover Page

Single-page, centered vertical layout, no header/footer:

| Element | Style |
|---|---|
| Logo placeholder | Top third, centered, 4 cm max height box |
| Project title | 28 pt, Calibri Light Bold, `#1F4E79`, centered |
| Subtitle | 16 pt, Calibri Light, `#44546A`, centered, 8 pt below title |
| Spacer | ~30% of page height |
| Author | 12 pt, Calibri, centered |
| Guide / Supervisor | 12 pt, Calibri, centered, labeled `Guide:` |
| Department | 11 pt, Calibri, centered |
| Institute | 11 pt, Calibri Bold, centered |
| Version | 10 pt, centered |
| Date | 10 pt, centered, bottom third of page |

All cover fields are Word content-control placeholders (not literal text) so Pandoc metadata (`title:`, `author:`, `date:` in YAML front matter) can populate them automatically where the Pandoc docx writer supports it; fields it doesn't support are left as clearly marked `[PLACEHOLDER]` bracketed text for manual fill-in.

---

## 20. Revision History

A table immediately following the cover page (or on its own page for thesis-length documents):

| Version | Date | Author | Description of Changes |
|---|---|---|---|
| 0.1 | — | — | Initial draft |

Table style: header row shaded `#1F4E79` with white bold text; identical structure to §6 professional table style; column widths fixed (Version 12%, Date 15%, Author 20%, Description 53%).

---

## 21. Table of Contents

- Automatically generated Word TOC field (`TOC \o "1-3" \h \z \u`), built from H1–H3 (outline levels 1–3) per §4.
- H4–H6 excluded from TOC to keep it navigable (a thesis-length document with 6 heading levels in the TOC becomes unusable).
- TOC entry style: dot leaders, right-aligned page numbers, hyperlinked, font Calibri 11 pt for level 1, 10.5 pt level 2, 10 pt level 3, with level-1 entries bold.
- Heading `Table of Contents` styled as H1 but excluded from the TOC itself (`TOC \o "1-3" \h \z \u \n` variant or manual exclusion via a "TOC Heading" style set to outline level 0).

---

## 22. List of Figures

Same mechanics as TOC but built from Figure caption `SEQ` fields (`TOC \c "Figure"`). Placed immediately after the Table of Contents. Uses the same dot-leader entry style as §21, 10.5 pt.

---

## 23. List of Tables

Identical mechanism, `TOC \c "Table"`, placed directly after the List of Figures.

---

## 24. Appendices

- Appendices begin on a new page after the References/Glossary/Index sections, with a distinct heading numbering scheme: `Appendix A`, `Appendix B`, … rather than numeric chapters.
- Heading style: same visual weight as H1 (§4) but using letter prefixes instead of numbers; a dedicated Word style **Appendix Heading** (aliased from Heading 1) is used so Pandoc can map `# Appendix: Title` to it via a Lua filter or a manual style override, since Pandoc's default numbering won't auto-switch to letters.
- Figures/tables inside appendices are numbered `Figure A.1`, `Table B.2`, etc., continuing the `SEQ` pattern with the appendix letter substituted for the chapter number.

---

## 25. References

- **Citation style: IEEE** — numbered, in order of first appearance, in square brackets (`[1]`, `[2]`).
- Reference list style: hanging indent 0.63 cm, 10.5 pt Calibri, single-spaced within an entry, 6 pt spacing between entries.
- Recommended tooling: Pandoc's citation processor (`--citeproc`) with a `references.bib` and the IEEE CSL style (`ieee.csl`) rather than hand-typed numbering, so citations stay consistent as content is reordered.

---

## 26. Glossary

- Two-column definition layout: term (bold, 11 pt) left-aligned in a narrow first column, definition in a wider second column — implemented as a borderless table for alignment control rather than tab stops, since Word tab leaders are brittle across long definitions.
- Alphabetical ordering, one entry per row, 6 pt spacing between rows, header row omitted (glossary tables don't need a repeated header).

---

## 27. Index

- Word's native `INDEX` field, built from `XE` (index entry) fields marked inline in the source content.
- Because Pandoc does not generate `XE` fields automatically, the index is treated as a **manual post-processing step**: after Pandoc conversion, marked terms are inserted via a small script or manually in Word, then `Insert > Index` is run.
- Two-column page layout for the index section specifically (a local section property override), since index entries are short and two columns roughly halves the page count.
- Recommendation: for most project documentation (API refs, guides), **omit the index** — it adds substantial manual maintenance for low payoff versus a good TOC + search. Reserve it for the thesis-report use case only.

---

## 28. Accessibility

| Concern | Rule |
|---|---|
| Color contrast | All text/background pairs meet WCAG AA (≥ 4.5:1 for body text, ≥ 3:1 for large/heading text) — verified against the palette in §1 |
| Color-only meaning | Never rely on color alone (callouts in §16 also carry a bold text label; links are also underlined per §10) |
| Font size floor | No body text below 9 pt anywhere in the document (footnotes are the floor) |
| Heading structure | Strict, non-skipping heading levels (no H1 → H3 without an intervening H2) so screen readers can navigate reliably |
| Alt text | Every image requires alt text populated from the Markdown `![alt text](...)` syntax — enforced as an authoring rule, not a template property |
| Table headers | Header rows marked as repeating header rows (`<w:tblHeader/>`) so screen readers and multi-page tables announce columns correctly |
| Reading order | Content-control placeholders on the cover page (§19) are ordered top-to-bottom to match visual layout for screen-reader tab order |

---

## 29. Printing

| Concern | Rule |
|---|---|
| Black-and-white friendliness | Every color-coded element (headings, callouts, links) also differs by **weight, border, or label text**, so meaning survives grayscale printing |
| A4 optimization | Default paper size is A4 (§2); a **US Letter variant** of the same template should be maintained in parallel (identical styles, page size 21.59 × 27.94 cm / margins re-tuned to 2.54 cm all round) for US-based collaborators |
| PDF export | Export via `File > Export > Create PDF/XPS` with "Best for printing" (embeds fonts, preserves bookmarks from heading structure) rather than "Best for electronic distribution," since the latter can subsample images below §12's DPI floor |
| Margins for physical binding | The 3.0 cm left margin (§2) and optional gutter (0.5 cm) leave room for spiral or perfect binding without clipping text |
| Ink coverage | Callout fills (§16) and code shading (§7) use light tints specifically to avoid heavy toner/ink use on documents with many code blocks |

---

## 30. Pandoc Compatibility — Required Word Styles

Pandoc maps Markdown constructs to Word **styles by name**. The reference `.docx` must define exactly these styles (and no superfluous extras, to keep the style gallery clean for anyone editing in Word):

| Word style name | Maps from (Markdown/Pandoc) | Defined in |
|---|---|---|
| `Normal` | Body paragraphs | §5 |
| `Title` | YAML `title:` metadata | §19 |
| `Subtitle` | YAML `subtitle:` metadata | §19 |
| `Heading 1`–`Heading 6` | `#`–`######` | §4 |
| `Source Code` (aliased **Code**) | fenced code blocks | §7 |
| `Verbatim Char` (inline code character style) | backtick inline code | §8 |
| `Block Text` (aliased **Quote**) | `>` blockquotes | §9 |
| `Caption` | `Figure`/`Table` captions, and Pandoc's auto-generated caption paragraphs | §11 |
| `TOC 1`–`TOC 3` | Table of Contents field entries | §21 |
| `Header` | Running header | §17 |
| `Footer` | Running footer | §18 |
| `Table Grid` / a custom **Project Table** style | Pipe tables / grid tables | §6 |
| `Hyperlink` (character style) | `[text](url)` | §10 |
| `First Paragraph` | First paragraph after a heading (no top spacing, avoids double-gap) | implicit in §5 |
| `Compact` | Tight list items (Pandoc uses this for lists without blank lines between items) | §6 |
| `Appendix Heading` | Manually applied for `# Appendix:` sections | §24 |

**No other custom styles should exist in the reference doc.** Extra unused styles bloat the style gallery and confuse contributors editing in Word directly.

**Command reference:**
```bash
# Generate a doc using the template
pandoc MASTER_TECHNICAL_DOCUMENTATION.md \
  --reference-doc=reference.docx \
  --toc --toc-depth=3 \
  --number-sections \
  --citeproc --bibliography=references.bib --csl=ieee.csl \
  --highlight-style=tango \
  -o output.docx

# Inspect current style names inside an existing reference.docx
pandoc -t markdown --extract-media=./media reference.docx > /dev/null
unzip -p reference.docx word/styles.xml | grep -o 'w:styleId="[^"]*"'
```

---

## Microsoft Word Implementation Steps

1. Create a new blank document; immediately go to **Layout > Size > A4** and set margins per §2 (**Layout > Margins > Custom Margins**, enter values, enable Mirror Margins only for the bound/thesis variant).
2. Open the **Styles pane** (Home tab, launcher icon). For each style in the §30 table:
   a. If it already exists as a Word built-in (Normal, Title, Heading 1–6, Caption, Header, Footer, Hyperlink, Quote → rename/alias to Block Text), right-click → **Modify** and apply the font, size, color, and spacing values from the corresponding section above.
   b. For styles with no Word built-in equivalent (Source Code, Appendix Heading, Project Table), use **New Style**, set **Style type** appropriately (Paragraph vs. Character vs. Table), and set **"Add to Styles gallery"** so contributors can find it.
3. Build the **callout boxes** (§16) as a one-row, one-column borderless-outer table for each type, with cell shading and a left border applied via **Table Properties > Borders and Shading**; save each as a **Quick Table** building block (Insert > Table > Quick Tables > Save Selection) so authors can insert them without recreating borders.
4. Build the **code block** style (§7) as a paragraph style with shading (Paragraph > Borders and Shading > Shading tab) and border (Borders tab, box, 0.75 pt, gray), font set to Consolas via the style's font properties, not manual formatting.
5. Set up **header/footer** (§17–18) with different-first-page enabled (Header & Footer Tools > Options > Different First Page), insert PAGE/NUMPAGES fields via Insert > Quick Parts > Field.
6. Build the **cover page** (§19) as content controls (Developer tab > Rich Text Content Control) so Pandoc metadata substitution and manual fill-in both work cleanly.
7. Insert TOC, List of Figures, List of Tables (§21–23) via References tab, using **Custom Table of Contents** dialogs configured to the outline/SEQ settings specified.
8. Insert section breaks (Layout > Breaks > Next Page) between front matter and body to allow the Roman → Arabic page-number restart (§18a), and before any landscape table sections (§6) to allow per-section orientation changes.
9. Save as **Word Template compatible reference** — i.e., a normal `.docx` (not `.dotx`) named `reference.docx`, since Pandoc's `--reference-doc` flag expects a `.docx`, not a template file.
10. Strip all body content from the document (Pandoc only reads **styles**, not text, from the reference doc) but leave one example paragraph of each style type if the file will also serve as a human-readable style guide — otherwise leave fully empty except for the mandatory front-matter/TOC fields.
11. Validate: run the command in the "Command reference" block above against a sample Markdown file and inspect the PDF output per the docx skill's verification step (convert to PDF, rasterize pages, visually check headings/code/tables/callouts render as specified).

---

## Best Practices

- Treat `reference.docx` as **code**: version-controlled, changelog-tracked (§20 pattern can apply to the template itself), never hand-edited per-document.
- Keep the style list in §30 as the single source of truth; if a new construct is needed (e.g., a new callout type), add the style to the reference doc **and** update this specification in the same change.
- Author all project Markdown assuming **strict heading nesting** (§28) — this is what keeps TOC, accessibility, and cross-references reliable.
- Pre-render all Mermaid diagrams (§13) as part of the build pipeline, never embed raw ```mermaid fences expecting Pandoc to handle them.
- Regenerate and re-check output after every Pandoc/LibreOffice version bump — OOXML rendering has historically drifted across versions.

## Common Mistakes

- Using `SOLID` shading instead of `CLEAR` for table/code backgrounds (renders solid black in some Word/LibreOffice combinations).
- Relying on manual character formatting (bold/color applied by hand) instead of named styles — breaks the moment someone regenerates the doc from Markdown, since Pandoc only respects styles, not ad hoc formatting, in the reference doc.
- Forgetting **"Different First Page"**, causing the header/footer to appear on the cover page.
- Skipping heading levels in source Markdown (e.g., `#` straight to `###`), which corrupts both the TOC and the accessibility outline.
- Embedding Mermaid diagrams at low source resolution, causing blurry output when Word/PDF scales them to the §12 width.
- Leaving unused legacy styles (e.g., default "List Paragraph," "Strong," "Emphasis" variants nobody uses) in the style gallery, which clutters the authoring experience for contributors.
- Mixing A4 and US Letter reference docs without clearly naming them (`reference.docx` vs `reference-letter.docx`) — leads to silently wrong margins for one audience.

## Future Extensibility

- **Dark-mode digital variant:** a parallel palette (inverted near-white text on near-black background) for teams that primarily consume documentation on-screen — same structural rules, swapped palette only.
- **Multi-language support:** hyphenation and font choices above are Latin-script-tuned; a CJK variant would need a secondary font stack (e.g., Microsoft YaHei / Noto Sans CJK) mapped into the same style names.
- **Automated style linting:** a CI script that unzips any regenerated `output.docx`, diffs `styles.xml` against `reference.docx`, and fails the build if unexpected inline formatting or orphaned styles appear — enforces the "styles, not manual formatting" discipline at scale.
- **Versioned template releases:** tag `reference.docx` releases (`v1.0`, `v1.1`, …) alongside this specification's own revision history, so historical documents can be regenerated against the exact template version they were originally built with.
