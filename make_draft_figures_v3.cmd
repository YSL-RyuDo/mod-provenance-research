@echo off
cd /d C:\research\mod-provenance-research

if not exist scripts mkdir scripts
if not exist paper mkdir paper
if not exist paper\figures mkdir paper\figures

echo [1/2] Generating paper figures...
python scripts\phase10_draft_figures_v3.py
if errorlevel 1 (
    echo.
    echo [ERROR] Figure generation failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Generated files:
dir /b paper\figures\fig*.pdf
echo.
echo DONE.
pause
