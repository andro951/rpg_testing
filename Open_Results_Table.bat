@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto failed

set "REPORT_PYTHON="
if exist ".venv-workbench\Scripts\python.exe" set "REPORT_PYTHON=.venv-workbench\Scripts\python.exe"
if not defined REPORT_PYTHON if exist ".venv\Scripts\python.exe" set "REPORT_PYTHON=.venv\Scripts\python.exe"
if not defined REPORT_PYTHON if exist ".local\audit-venv\Scripts\python.exe" set "REPORT_PYTHON=.local\audit-venv\Scripts\python.exe"
if not defined REPORT_PYTHON set "REPORT_PYTHON=python"

echo Generating the results table from saved results...
"%REPORT_PYTHON%" -m reporting.report
if errorlevel 1 goto failed

"%REPORT_PYTHON%" -m reporting.server
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo Could not generate or open the results table. See the error above.
pause
exit /b 1
