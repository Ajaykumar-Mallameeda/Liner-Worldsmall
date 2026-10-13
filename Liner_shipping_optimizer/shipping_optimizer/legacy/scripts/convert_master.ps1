<#
.SYNOPSIS
    Master Conversion Script — AI Vessel Routing System DOCX Generation (PowerShell)
.DESCRIPTION
    Converts three markdown documentation files into professional DOCX documents.
    Uses reference.docx as the official Word style template.
    Renders Mermaid diagrams, applies pandoc-crossref, and validates output.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$StartTime = Get-Date
$env:PYTHONIOENCODING = "utf-8"

# ── Configuration ──
$ReferenceDoc = Join-Path $ProjectRoot "reference.docx"
$AssetsDir = Join-Path $ProjectRoot "docs" "generated" "assets"
$SvgDir = Join-Path $AssetsDir "svg"
$PreprocessedDir = Join-Path $ProjectRoot "docs" "generated"

$Files = @(
    @{ Input = "MASTER_TECHNICAL_DOCUMENTATION_V2.md"; Title = "Master Technical Documentation V2 — AI Vessel Routing System" },
    @{ Input = "ARCHITECTURE_REFERENCE.md"; Title = "Architecture Reference — AI Vessel Routing System" },
    @{ Input = "CODE_REFERENCE.md"; Title = "Code Reference — AI Vessel Routing System" }
)

# ── Helper Functions ──
function Write-Step($Message) {
    Write-Host "`n>>> $Message" -ForegroundColor Cyan
}

function Test-Command($Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "  ✗ MISSING: $Name" -ForegroundColor Red
        return $false
    }
    Write-Host "  ✓ $Name: $($cmd.Source)" -ForegroundColor Green
    return $true
}

# ── Step 1: Verify Dependencies ──
Write-Step "Step 1: Verifying Dependencies"
$depsOk = $true
$depsOk = (Test-Command pandoc) -and $depsOk
$depsOk = (Test-Command pandoc-crossref) -and $depsOk
$depsOk = (Test-Command python) -and $depsOk
$depsOk = (Test-Command node) -and $depsOk
$depsOk = (Test-Command mmdc.cmd) -and $depsOk

if (-not $depsOk) {
    Write-Host "`n⚠ Some dependencies are missing. Install them and re-run." -ForegroundColor Yellow
    exit 1
}

# Check reference.docx
if (-not (Test-Path $ReferenceDoc)) {
    Write-Host "  ✗ reference.docx not found at $ReferenceDoc" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ reference.docx" -ForegroundColor Green

# ── Step 2: Preprocess Markdown (Mermaid rendering, formatting fixes) ──
Write-Step "Step 2: Preprocessing Markdown Files"
Push-Location $ProjectRoot
try {
    python scripts/preprocess_markdown.py 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Preprocessing failed" }
} finally {
    Pop-Location
}

# ── Step 3: Convert SVGs to PNGs for Pandoc DOCX embedding ──
Write-Step "Step 3: Converting SVG Diagrams to PNG"
Push-Location $ProjectRoot
try {
    $svgFiles = Get-ChildItem -Path $SvgDir -Filter "*.svg"
    $count = 0
    foreach ($svg in $svgFiles) {
        $pngPath = [System.IO.Path]::ChangeExtension($svg.FullName, ".png")
        Write-Progress -Activity "Converting SVGs to PNGs" -Status "$($svg.Name)" -PercentComplete (($count / $svgFiles.Count) * 100)
        node -e "
            const sharp = require('sharp');
            sharp('$($svg.FullName.Replace("'","''"))')
                .resize({ width: 2400, withoutEnlargement: true })
                .png()
                .toFile('$($pngPath.Replace("'","''"))')
                .then(() => { process.exit(0); })
                .catch(e => { console.error(e.message); process.exit(1); });
        " 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $count++ }
    }
    Write-Host "  ✓ Converted $count/$($svgFiles.Count) SVGs to PNG" -ForegroundColor Green
} finally {
    Pop-Location
}

# ── Step 4: Update Image References ──
Write-Step "Step 4: Updating Image References to PNG"
Push-Location $ProjectRoot
try {
    Get-ChildItem -Path $PreprocessedDir -Filter "*_preprocessed.md" | ForEach-Object {
        (Get-Content $_.FullName) -replace '\.svg\)', '.png)' | Set-Content $_.FullName -Encoding utf8
        Write-Host "  ✓ Updated $($_.Name)" -ForegroundColor Green
    }
} finally {
    Pop-Location
}

# ── Step 5: Generate DOCX Files ──
Write-Step "Step 5: Generating DOCX Documents"
Push-Location $ProjectRoot
try {
    foreach ($f in $Files) {
        $inputMd = Join-Path $PreprocessedDir "$($f.Input.Replace('.md', '_preprocessed.md'))"
        $outputDocx = Join-Path $PreprocessedDir $f.Input.Replace('.md', '.docx')
        $title = $f.Title

        Write-Host "  Converting $($f.Input)..." -ForegroundColor Yellow
        $result = pandoc $inputMd `
            -o $outputDocx `
            --reference-doc=$ReferenceDoc `
            --filter pandoc-crossref `
            --toc --toc-depth 4 `
            --metadata title="$title" `
            --metadata date="2026-07-04" `
            -f markdown -t docx `
            --wrap=preserve `
            --resource-path=$PreprocessedDir `
            2>&1

        if ($LASTEXITCODE -eq 0) {
            $size = (Get-Item $outputDocx).Length / 1KB
            Write-Host "  ✓ $($outputDocx.Name) ($([math]::Round($size)) KB)" -ForegroundColor Green
        } else {
            Write-Host "  ✗ FAILED: $($f.Input)" -ForegroundColor Red
            Write-Host "  $result"
            exit 1
        }
    }
} finally {
    Pop-Location
}

# ── Step 6: Validate Output ──
Write-Step "Step 6: Validating DOCX Output"
Push-Location $ProjectRoot
try {
    foreach ($f in $Files) {
        $outputDocx = Join-Path $PreprocessedDir $f.Input.Replace('.md', '.docx')
        if (Test-Path $outputDocx) {
            $size = (Get-Item $outputDocx).Length
            $name = Split-Path $outputDocx -Leaf
            if ($size -gt 10000) {
                Write-Host "  ✓ $name ($([math]::Round($size / 1KB)) KB)" -ForegroundColor Green
            } else {
                Write-Host "  ⚠ $name appears too small ($([math]::Round($size / 1KB)) KB)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  ✗ $($f.Input.Replace('.md', '.docx')) NOT FOUND" -ForegroundColor Red
        }
    }
} finally {
    Pop-Location
}

# ── Summary ──
$EndTime = Get-Date
$Duration = $EndTime - $StartTime
Write-Step "Conversion Complete!"
Write-Host "  Elapsed time: $($Duration.Hours)h $($Duration.Minutes)m $($Duration.Seconds)s" -ForegroundColor Green
Write-Host "  Output directory: $PreprocessedDir" -ForegroundColor Green
Write-Host "  Files:" -ForegroundColor Green
foreach ($f in $Files) {
    $docx = Join-Path $PreprocessedDir $f.Input.Replace('.md', '.docx')
    if (Test-Path $docx) {
        Write-Host "    ✓ $($f.Input.Replace('.md', '.docx'))" -ForegroundColor Green
    }
}
