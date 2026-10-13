#!/usr/bin/env bash
# ============================================================================
# Master Conversion Script — AI Vessel Routing System DOCX Generation (Bash)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
START_TIME="${SECONDS}"

# ---- Configuration ----
REFERENCE_DOC="${PROJECT_ROOT}/reference.docx"
ASSETS_DIR="${PROJECT_ROOT}/docs/generated/assets"
SVG_DIR="${ASSETS_DIR}/svg"
PREPROCESSED_DIR="${PROJECT_ROOT}/docs/generated"

FILES=(
    "MASTER_TECHNICAL_DOCUMENTATION_V2.md:Master Technical Documentation V2 — AI Vessel Routing System"
    "ARCHITECTURE_REFERENCE.md:Architecture Reference — AI Vessel Routing System"
    "CODE_REFERENCE.md:Code Reference — AI Vessel Routing System"
)

# ---- Colors ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

step()  { echo -e "\n${CYAN}>>> ${*}${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} ${*}"; }
fail()  { echo -e "  ${RED}✗${NC} ${*}"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} ${*}"; }

# ---- Step 1: Verify Dependencies ----
step "Step 1: Verifying Dependencies"

for cmd in pandoc pandoc-crossref python3 python node mmdc.cmd; do
    if command -v "${cmd}" &>/dev/null; then
        ok "${cmd}"
    else
        fail "${cmd} — install and re-run"
        HAS_MISSING=1
    fi
done

if [[ ! -f "${REFERENCE_DOC}" ]]; then
    fail "reference.docx not found at ${REFERENCE_DOC}"
    HAS_MISSING=1
fi

if [[ -n "${HAS_MISSING:-}" ]]; then
    warn "Some dependencies missing. Install them and re-run."
    exit 1
fi
ok "reference.docx"

# ---- Step 2: Preprocess Markdown ----
step "Step 2: Preprocessing Markdown Files"
cd "${PROJECT_ROOT}"
python scripts/preprocess_markdown.py

# ---- Step 3: Convert SVGs to PNGs ----
step "Step 3: Converting SVG Diagrams to PNG"
cd "${PROJECT_ROOT}"
COUNT=0
TOTAL=$(find "${SVG_DIR}" -name '*.svg' 2>/dev/null | wc -l)
for svg in "${SVG_DIR}"/*.svg; do
    [[ -f "${svg}" ]] || continue
    png="${svg%.svg}.png"
    if node -e "
        const sharp = require('sharp');
        sharp('${svg}').resize({width:2400,withoutEnlargement:true}).png().toFile('${png}').then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(1)});
    " 2>/dev/null; then
        COUNT=$((COUNT + 1))
    fi
done
ok "Converted ${COUNT}/${TOTAL} SVGs to PNG"

# ---- Step 4: Update Image References ----
step "Step 4: Updating Image References to PNG"
cd "${PROJECT_ROOT}"
for f in "${PREPROCESSED_DIR}"/*_preprocessed.md; do
    sed -i 's/\.svg)/\.png)/g' "${f}"
    ok "Updated $(basename "${f}")"
done

# ---- Step 5: Generate DOCX Files ----
step "Step 5: Generating DOCX Documents"
cd "${PROJECT_ROOT}"

for entry in "${FILES[@]}"; do
    IFS=':' read -r filename title <<< "${entry}"
    base="${filename%.md}"
    input_md="${PREPROCESSED_DIR}/${base}_preprocessed.md"
    output_docx="${PREPROCESSED_DIR}/${base}.docx"

    echo "  Converting ${filename} → ${base}.docx"
    pandoc "${input_md}" \
        -o "${output_docx}" \
        --reference-doc="${REFERENCE_DOC}" \
        --filter pandoc-crossref \
        --toc --toc-depth 4 \
        --metadata title="${title}" \
        --metadata date="2026-07-04" \
        -f markdown -t docx \
        --wrap=preserve \
        --resource-path="${PREPROCESSED_DIR}" 2>&1

    if [[ -f "${output_docx}" ]]; then
        size_kb=$(du -k "${output_docx}" | cut -f1)
        ok "${base}.docx (${size_kb} KB)"
    else
        fail "${base}.docx generation failed"
        exit 1
    fi
done

# ---- Step 6: Validate Output ----
step "Step 6: Validating DOCX Output"
cd "${PROJECT_ROOT}"
for docx in "${PREPROCESSED_DIR}"/*.docx; do
    [[ -f "${docx}" ]] || continue
    size=$(stat -c%s "${docx}" 2>/dev/null || stat -f%z "${docx}" 2>/dev/null)
    name=$(basename "${docx}")
    if [[ "${size}" -gt 10000 ]]; then
        ok "${name} ($(( size / 1024 )) KB)"
    else
        warn "${name} appears too small (${size} bytes)"
    fi
done

# ---- Summary ----
ELAPSED=$(( SECONDS - START_TIME ))
step "Conversion Complete!"
ok "Elapsed time: $(( ELAPSED / 3600 ))h $(( (ELAPSED % 3600) / 60 ))m $(( ELAPSED % 60 ))s"
ok "Output directory: ${PREPROCESSED_DIR}"
echo "  Files:"
for entry in "${FILES[@]}"; do
    IFS=':' read -r filename title <<< "${entry}"
    base="${filename%.md}"
    docx="${PREPROCESSED_DIR}/${base}.docx"
    if [[ -f "${docx}" ]]; then
        ok "  ${base}.docx"
    fi
done
