@echo off
REM ===========================================================================
REM Master Conversion Script — AI Vessel Routing System DOCX Generation (Batch)
REM ===========================================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "START_TIME=%TIME%"

REM ---- Configuration ----
set "REFERENCE_DOC=%PROJECT_ROOT%\reference.docx"
set "ASSETS_DIR=%PROJECT_ROOT%\docs\generated\assets"
set "SVG_DIR=%ASSETS_DIR%\svg"
set "PREPROCESSED_DIR=%PROJECT_ROOT%\docs\generated"

REM ---- Step 1: Verify Dependencies ----
echo.
echo ^>^>^> Step 1: Verifying Dependencies

where pandoc >nul 2>&1 && (echo  [OK] pandoc) || (echo  [FAIL] pandoc && exit /b 1)
where pandoc-crossref >nul 2>&1 && (echo  [OK] pandoc-crossref) || (echo  [FAIL] pandoc-crossref && exit /b 1)
where python >nul 2>&1 && (echo  [OK] python) || (echo  [FAIL] python && exit /b 1)
where node >nul 2>&1 && (echo  [OK] node) || (echo  [FAIL] node && exit /b 1)
where mmdc.cmd >nul 2>&1 && (echo  [OK] mmdc.cmd) || (echo  [FAIL] mmdc.cmd && exit /b 1)

if not exist "%REFERENCE_DOC%" (
    echo  [FAIL] reference.docx not found
    exit /b 1
)
echo  [OK] reference.docx

REM ---- Step 2: Preprocess Markdown ----
echo.
echo ^>^>^> Step 2: Preprocessing Markdown Files
cd /d "%PROJECT_ROOT%"
python scripts/preprocess_markdown.py
if %ERRORLEVEL% neq 0 (
    echo  [FAIL] Preprocessing failed
    exit /b 1
)

REM ---- Step 3: Convert SVGs to PNGs ----
echo.
echo ^>^>^> Step 3: Converting SVG Diagrams to PNG
cd /d "%PROJECT_ROOT%"
set COUNT=0
for %%f in ("%SVG_DIR%\*.svg") do (
    set "PNG_PATH=%%~dpnf.png"
    node -e "const sharp=require('sharp');sharp('%%f').resize({width:2400,withoutEnlargement:true}).png().toFile('!PNG_PATH!').then(()=>{process.exit(0)}).catch(e=>{console.error(e.message);process.exit(1)})"
    if !ERRORLEVEL! equ 0 set /a COUNT+=1
)
echo  [OK] Converted %COUNT% SVGs to PNG

REM ---- Step 4: Update Image References ----
echo.
echo ^>^>^> Step 4: Updating Image References to PNG
cd /d "%PROJECT_ROOT%"
for %%f in ("%PREPROCESSED_DIR%\*_preprocessed.md") do (
    powershell -Command "(Get-Content '%%f') -replace '\.svg\)', '.png)' | Set-Content '%%f' -Encoding utf8"
    echo  [OK] Updated %%~nxf
)

REM ---- Step 5: Generate DOCX Files ----
echo.
echo ^>^>^> Step 5: Generating DOCX Documents
cd /d "%PROJECT_ROOT%"

set "FILE1_NAME=MASTER_TECHNICAL_DOCUMENTATION_V2"
set "FILE1_TITLE=Master Technical Documentation V2 — AI Vessel Routing System"
set "FILE2_NAME=ARCHITECTURE_REFERENCE"
set "FILE2_TITLE=Architecture Reference — AI Vessel Routing System"
set "FILE3_NAME=CODE_REFERENCE"
set "FILE3_TITLE=Code Reference — AI Vessel Routing System"

call :convert_file %FILE1_NAME% "%FILE1_TITLE%"
call :convert_file %FILE2_NAME% "%FILE2_TITLE%"
call :convert_file %FILE3_NAME% "%FILE3_TITLE%"

goto :validation

:convert_file
set "INPUT_MD=%PREPROCESSED_DIR%\%~1_preprocessed.md"
set "OUTPUT_DOCX=%PREPROCESSED_DIR%\%~1.docx"
set "TITLE=%~2"
echo  Converting %~1.docx...
pandoc "%INPUT_MD%" -o "%OUTPUT_DOCX%" --reference-doc="%REFERENCE_DOC%" --filter pandoc-crossref --toc --toc-depth 4 --metadata title="%TITLE%" --metadata date="2026-07-04" -f markdown -t docx --wrap=preserve --resource-path="%PREPROCESSED_DIR%" 2>&1
if %ERRORLEVEL% equ 0 (
    echo  [OK] %~1.docx generated
) else (
    echo  [FAIL] %~1.docx failed
    exit /b 1
)
goto :eof

:validation
REM ---- Step 6: Validate Output ----
echo.
echo ^>^>^> Step 6: Validating DOCX Output
for %%f in ("%PREPROCESSED_DIR%\*.docx") do (
    set "SIZE=%%~zf"
    if !SIZE! gtr 10000 (
        echo  [OK] %%~nxf (!SIZE:~0,-3! KB)
    ) else (
        echo  [WARN] %%~nxf is too small (!SIZE! bytes)
    )
)

REM ---- Summary ----
echo.
echo ========================================
echo  Conversion Complete!
echo  Output: %PREPROCESSED_DIR%
echo ========================================
echo.

endlocal
