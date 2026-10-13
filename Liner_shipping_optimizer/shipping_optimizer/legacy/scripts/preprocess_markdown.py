#!/usr/bin/env python3
"""
Preprocessing script for DOCX conversion pipeline.
Handles:
  1. Fix spacing issues (blank lines before code blocks)
  2. Add language specifiers to unlabeled code blocks
  3. Extract Mermaid diagrams, render to SVG
  4. Replace with image references
  5. Output clean markdown ready for pandoc
"""

import re
import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

# Import caption and explanation mapping
sys.path.insert(0, str(Path(__file__).resolve().parent))
from caption_map import get_mermaid_caption, get_dot_captions

# ── Configuration ──────────────────────────────────────────────
REFERENCE_DOC = Path(__file__).resolve().parent.parent / "reference.docx"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "generated"
ASSETS_DIR = OUTPUT_DIR / "assets" / "svg"
MERMAID_DIR = OUTPUT_DIR / "assets" / "mermaid"

# Mermaid CLI config
MMDC_CONFIG = os.path.join(os.environ["USERPROFILE"], ".mmdc_config.json")

# ── Helpers ────────────────────────────────────────────────────

def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)


def fix_spacing(text):
    """Add blank lines before code blocks if missing."""
    # Fix: text immediately followed by ``` (no blank line)
    # Pattern: non-blank line ending in text, then a ``` line
    text = re.sub(r'([^\n])\n(```)', r'\1\n\n\2', text)
    return text


def fix_code_language(text):
    """Add language specifiers to unlabeled fenced code blocks.

    Properly tracks open/close fence state to avoid corrupting
    closing fences or already-labeled code blocks.

    Detect content type:
      - directory trees / ASCII art → 'text'
      - prompt/response text → 'text'
      - shell commands → 'bash'
      - Unclear → leave as 'text'
    """
    lines = text.split('\n')
    result = []
    in_code_block = False
    inside_mermaid = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Detect code fence
        if stripped.startswith('```'):
            if not in_code_block:
                # Opening fence
                in_code_block = True
                # Check if it already has a language or is mermaid
                rest = stripped[3:].strip()
                if rest == '':
                    # No language specified - detect it
                    # Look at content until closing fence
                    content_lines = []
                    j = i + 1
                    while j < len(lines) and not lines[j].lstrip().startswith('```'):
                        content_lines.append(lines[j])
                        j += 1
                    content = '\n'.join(content_lines)
                    lang = detect_language(content)
                    if lang:
                        result.append(f'```{lang}')
                        inside_mermaid = (lang == 'mermaid')
                    else:
                        result.append('```text')
                        inside_mermaid = False
                else:
                    # Already has a language
                    result.append(line)
                    inside_mermaid = (rest == 'mermaid')
            else:
                # Closing fence
                in_code_block = False
                inside_mermaid = False
                result.append('```')
        else:
            result.append(line)
        i += 1

    return '\n'.join(result)


def detect_language(content):
    """Detect the language for a code block from its content."""
    if not content.strip():
        return 'text'

    first_lines = content.strip().split('\n')[:5]
    first_line = first_lines[0] if first_lines else ''

    # JSON detection
    if content.strip().startswith('{') and ('"type"' in content or '"name"' in content or '"id"' in content):
        return 'json'

    if content.strip().startswith('[') and '"' in content[:50]:
        return 'json'

    # Python detection
    python_keywords = ['def ', 'import ', 'from ', 'class ', 'if __name__', 'return ', 'elif ', 'else:',
                       'try:', 'except:', 'with ', 'async ', 'await ']
    if any(kw in content for kw in python_keywords):
        return 'python'

    # JavaScript detection
    js_keywords = ['function ', 'const ', 'let ', 'var ', '=>', 'import React', 'export ',
                   'require(', 'module.exports']
    if any(kw in content for kw in js_keywords):
        return 'javascript'

    # SQL detection
    sql_keywords = ['SELECT ', 'FROM ', 'WHERE ', 'INSERT INTO', 'CREATE TABLE', 'ALTER TABLE',
                    'JOIN ', 'GROUP BY', 'ORDER BY']
    if any(kw.upper().strip() in content.upper() for kw in sql_keywords):
        return 'sql'

    # Bash/shell detection
    bash_indicators = ['#!/', 'apt-get', 'npm ', 'pip ', 'git ', 'docker ', 'cd ', 'export ',
                       'uvicorn ', 'python ', 'node ', '&& ', '; ']
    if any(content.strip().startswith(kw) for kw in bash_indicators):
        return 'bash'

    # YAML/TOML detection (e.g., .env files)
    if '=' in first_line and not first_line.strip().startswith('#'):
        # Could be env file or config
        if not any(c in first_line for c in ['{', '[', '(']):
            # Check if it's all key=value pairs
            lines = content.strip().split('\n')
            keyval_count = sum(1 for l in lines if '=' in l and not l.strip().startswith('#'))
            if keyval_count > len(lines) * 0.5:
                return 'env'

    # Directory tree / ASCII art detection
    tree_indicators = ['├──', '└──', '│', '──', '|--', '`--']
    if any(ind in content for ind in tree_indicators):
        return 'text'

    # ASCII flow diagrams
    if '-->' in content or '->' in content or '|>' in content:
        # Check if it looks like a diagram rather than code
        ascii_art_lines = sum(1 for l in content.split('\n')
                             if re.search(r'[│┌┐└┘├┤┬┴┼─═║╔╗╚╝╠╣╦╩╬<>^v]', l))
        if ascii_art_lines > 2:
            return 'text'

    # Tabular data / listings
    if content.strip().startswith('Route') or '   ' in content:
        return 'text'

    # Default based on first line
    if re.match(r'^[a-zA-Z0-9_/.-]+\s*$', first_line):
        # Could be a file path or module name
        return 'text'

    return 'text'


def extract_and_render_mermaid(markdown_text, svg_dir, mermaid_dir, base_name):
    """Extract Mermaid code blocks, render to PNG via mmdc (Chrome), replace with image refs.

    Uses DIRECT mmdc->PNG rendering (not SVG->sharp->PNG) to preserve
    foreignObject text labels that no SVG converter supports.

    Uses the caption_map.py module to generate descriptive, human-readable
    captions instead of exposing implementation syntax (e.g., "graph LR").

    Returns:
        tuple: (modified_markdown, list_of_rendered_pngs)
    """
    svg_dir = Path(svg_dir)
    mermaid_dir = Path(mermaid_dir)
    ensure_dir(svg_dir)
    ensure_dir(mermaid_dir)

    rendered = []
    global_diagram_idx = [0]  # mutable counter for closure access

    def render_mermaid(match):
        nonlocal rendered

        # Extract the content
        code_block = match.group(0)
        inner = match.group(1)

        # Get the first line as diagram type
        lines = inner.strip().split('\n')
        diagram_type_line = lines[0].strip() if lines else 'unknown'

        # Create a unique filename
        type_key = diagram_type_line.split()[0] if diagram_type_line else 'diagram'
        global_diagram_idx[0] += 1
        idx = global_diagram_idx[0]

        # Use sequential index for clean filenames
        png_filename = f"{base_name}_mermaid_{idx:03d}.png"
        png_path = svg_dir / png_filename

        mmd_filename = f"{base_name}_mermaid_{idx:03d}.mmd"
        mmd_path = mermaid_dir / mmd_filename

        # Write the .mmd file
        with open(mmd_path, 'w', encoding='utf-8') as f:
            f.write(inner)

        # Render DIRECTLY to PNG via mmdc (Chrome renders foreignObject correctly)
        mmdc_cmd = 'mmdc.cmd'
        print(f"  Rendering Mermaid diagram: {png_filename}...")
        result = subprocess.run(
            [mmdc_cmd, '-i', str(mmd_path), '-o', str(png_path),
             '-p', MMDC_CONFIG, '-b', 'white', '-s', '3'],
            capture_output=True, text=True, timeout=60, shell=True
        )

        if result.returncode == 0 and png_path.exists():
            print(f"    [OK] Rendered to PNG ({png_path.stat().st_size / 1024:.0f} KB)")
            rendered.append(str(png_path))

            # Get descriptive caption from caption_map.py
            caption, explanation = get_mermaid_caption(base_name, idx)

            # Use descriptive caption if available, otherwise fall back to type
            if caption:
                desc = caption
                # Add explanation as a markdown block quote after the image
                explanation_text = f"\n\n**{desc}.** "
                if explanation:
                    explanation_text += explanation
                explanation_text += "\n"
            else:
                desc = f"{type_key} Diagram"
                explanation_text = "\n\n"

            svg_rel = os.path.join('assets/svg', png_filename).replace('\\', '/')
            return f'![{desc}]({svg_rel}){{#fig:diagram-{idx}}}{explanation_text}'
        else:
            print(f"    [FAIL] mmdc render failed for {mmd_filename}: {result.stderr.strip()[:200]}")
            # Keep the original Mermaid code block as fallback
            return f'```mermaid\n{inner}\n```'

    # Replace Mermaid blocks with image references
    pattern = r'```mermaid\n([\s\S]*?)```'
    modified = re.sub(pattern, render_mermaid, markdown_text)

    return modified, rendered


def extract_tables_for_landscape(markdown_text):
    """Identify wide tables (6+ columns) and wrap them for landscape pages.

    This is handled by a pandoc Lua filter rather than preprocessing.
    Returns the text unchanged; the Lua filter will add landscape instructions.
    """
    # We'll handle this in the pandoc Lua filter
    return markdown_text


def preprocess_file(input_path, output_path, base_name=None):
    """Full preprocessing pipeline for one markdown file."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    if base_name is None:
        base_name = input_path.stem

    print(f"\n{'='*60}")
    print(f"Preprocessing: {input_path.name}")
    print(f"{'='*60}")

    # Read input
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Step 1: Fix spacing
    print("  Step 1: Fixing spacing...")
    text = fix_spacing(text)

    # Step 2: Fix code language specifiers
    print("  Step 2: Adding language specifiers...")
    text = fix_code_language(text)

    # Step 3: Extract and render Mermaid diagrams
    print(f"  Step 3: Rendering Mermaid diagrams...")
    text, rendered_svgs = extract_and_render_mermaid(
        text, ASSETS_DIR, MERMAID_DIR, base_name
    )

    # Step 4: Ensure the output directory exists
    ensure_dir(output_path.parent)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"\n  [OK] Written to: {output_path}")
    print(f"  [OK] Mermaid diagrams rendered: {len(rendered_svgs)}")

    return rendered_svgs


def generate_pandoc_command(input_md, output_docx, reference_doc=None):
    """Generate the pandoc command for a single document."""
    cmd = ['pandoc']

    # Input
    cmd.append(str(input_md))

    # Output
    cmd.extend(['-o', str(output_docx)])

    # Reference docx for styling
    if reference_doc and reference_doc.exists():
        cmd.extend(['--reference-doc', str(reference_doc)])

    # Filters
    cmd.extend(['--filter', 'pandoc-crossref'])

    # Table of Contents
    cmd.extend(['--toc', '--toc-depth', '4'])

    # Metadata
    cmd.extend(['--metadata', 'date:2026-07-04'])

    # From/To format
    cmd.extend(['-f', 'markdown', '-t', 'docx'])

    # HTML/raw HTML not allowed
    cmd.append('--from=markdown-raw_html')

    # No wrap in code blocks
    cmd.append('--wrap=preserve')

    # Resource path for images - use the docs/generated directory
    resource_path = Path(__file__).resolve().parent.parent / "docs" / "generated"
    cmd.extend(['--resource-path', str(resource_path)])

    return cmd


def inject_dot_diagrams(markdown_text, doc_name):
    """Inject DOT architecture diagrams into the preprocessed markdown.

    Uses descriptive captions and technical explanations from caption_map.py.
    Uses high-resolution PNG images (_hires suffix) for publication quality.
    Adds landscape page break instructions for large diagrams.
    """
    diagram_dir = "assets/diagrams/png"

    # Get caption/explanations from caption_map
    dot_entries = get_dot_captions(doc_name)
    if not dot_entries:
        return markdown_text

    # Diagram filenames in order
    diagram_filenames = {
        'MASTER_TECHNICAL_DOCUMENTATION_V2': [
            "00_overall_system", "01_multi_agent", "02_backend_architecture",
            "03_frontend_architecture", "04_optimization_pipeline", "05_data_flow",
            "06_validation_pipeline", "07_llm_integration", "08_configuration",
            "09_repository_structure",
        ],
        'ARCHITECTURE_REFERENCE': [
            "00_overall_system", "01_multi_agent", "02_backend_architecture",
            "06_validation_pipeline", "07_llm_integration", "08_configuration",
        ],
        'CODE_REFERENCE': [
            "09_repository_structure", "04_optimization_pipeline", "05_data_flow",
        ],
    }

    names = diagram_filenames.get(doc_name, [])
    if not names or not dot_entries:
        return markdown_text

    # Build the injection block with architecture overview
    injection_lines = []
    injection_lines.append("\n\n")
    injection_lines.append("---\n\n")
    injection_lines.append("## Architecture Overview Diagrams\n\n")
    injection_lines.append("The following architecture diagrams are generated directly from the source code implementation using Graphviz DOT (v15.1.0). Each figure includes a detailed technical explanation of component responsibilities, interactions, and the relevant source files. These diagrams serve as a visual index to the complete system architecture.\n\n")

    for i, (name, (caption, explanation)) in enumerate(zip(names, dot_entries)):
        # Use hires PNG for best quality in DOCX
        hires_path = f"{diagram_dir}/{name}_hires.png"
        hires_full = os.path.join(
            Path(__file__).resolve().parent.parent,
            "docs", "generated", hires_path
        )

        if os.path.exists(hires_full.replace('_hires', '_hires')):
            img_path = hires_path
        else:
            img_path = f"{diagram_dir}/{name}.png"

        fig_id = f"fig:arch-{name}"
        injection_lines.append(f"![{caption}]({img_path}){{#{fig_id}}}\n\n")
        injection_lines.append(f"**{caption}.** {explanation}\n\n")
        injection_lines.append("---\n\n")

    injection_block = "".join(injection_lines)

    # Inject after the first heading (H1)
    lines = markdown_text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# ') and i < 5:
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].startswith('## ') or (lines[j].strip() == '' and j + 1 < len(lines) and lines[j+1].startswith('## ')):
                    insert_pos = j
                    break
            else:
                insert_pos = i + 2
            lines.insert(insert_pos, injection_block)
            break

    return '\n'.join(lines)


def main():
    """Main entry point."""
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    ensure_dir(OUTPUT_DIR)

    # Files to process
    files = [
        {
            'input': project_root / 'MASTER_TECHNICAL_DOCUMENTATION_V2.md',
            'output': OUTPUT_DIR / 'MASTER_TECHNICAL_DOCUMENTATION_V2_preprocessed.md',
            'docx': OUTPUT_DIR / 'MASTER_TECHNICAL_DOCUMENTATION_V2.docx',
            'title': 'Master Technical Documentation V2 — AI Vessel Routing System',
        },
        {
            'input': project_root / 'ARCHITECTURE_REFERENCE.md',
            'output': OUTPUT_DIR / 'ARCHITECTURE_REFERENCE_preprocessed.md',
            'docx': OUTPUT_DIR / 'ARCHITECTURE_REFERENCE.docx',
            'title': 'Architecture Reference — AI Vessel Routing System',
        },
        {
            'input': project_root / 'CODE_REFERENCE.md',
            'output': OUTPUT_DIR / 'CODE_REFERENCE_preprocessed.md',
            'docx': OUTPUT_DIR / 'CODE_REFERENCE.docx',
            'title': 'Code Reference — AI Vessel Routing System',
        },
    ]

    all_rendered = {}

    # Preprocess each file
    for f in files:
        svgs = preprocess_file(
            f['input'], f['output'],
            base_name=f['input'].stem
        )
        all_rendered[f['input'].stem] = svgs

        # Inject DOT architecture diagrams
        print("  Step 4: Injecting DOT architecture diagrams...")
        with open(f['output'], 'r', encoding='utf-8') as fp:
            text = fp.read()
        text = inject_dot_diagrams(text, f['input'].stem)
        with open(f['output'], 'w', encoding='utf-8') as fp:
            fp.write(text)
        print(f"    [OK] Injected architecture diagrams")

    print(f"\n{'='*60}")
    print("Preprocessing complete!")
    print(f"{'='*60}")
    print(f"Total diagrams rendered: {sum(len(v) for v in all_rendered.values())}")

    # Print pandoc commands
    print(f"\n{'='*60}")
    print("Pandoc conversion commands:")
    print(f"{'='*60}")
    for f in files:
        cmd = generate_pandoc_command(
            f['output'], f['docx'], REFERENCE_DOC
        )
        cmd_str = ' '.join(str(c) for c in cmd)
        print(f"\n  {f['docx'].name}:")
        print(f"  {cmd_str}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
