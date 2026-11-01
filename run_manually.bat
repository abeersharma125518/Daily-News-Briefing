@echo off
cd /d "%~dp0"

rem Prefer the py launcher, fall back to python on PATH.
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py"

%PY% main.py --log-file "%~dp0logs\manual_run.log"
pause
