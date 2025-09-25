@echo off
setlocal

rem Change to the directory of this script
pushd %~dp0

rem Try to activate a local virtual environment
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Could not find virtual environment at '.venv' or 'venv'.
    echo Create one with: python -m venv .venv
    exit /b 1
)

rem Run the UI
python run_ui.py

popd
endlocal
