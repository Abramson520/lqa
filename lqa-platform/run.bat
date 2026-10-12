@echo off
rem LQA Web workbench launcher (ASCII-only comments to avoid GBK/UTF-8 mangling)
cd /d "%~dp0"

set "PYTHONUNBUFFERED=1"

rem Resolve interpreter: LQA_PY override > project .venv > ASCII-path venv.
rem We probe by importing the actual hard dependency (fastapi), not just `import sys`:
rem a venv that cannot boot (e.g. Chinese-path pyvenv.cfg) must be skipped, and a
rem venv without the installed packages must not be selected either.
set "PY="
call :probe_venv "%LQA_PY%" && goto :found
call :probe_venv ".venv\Scripts\python.exe" && goto :found
call :probe_venv "E:\lqa_venv\Scripts\python.exe" && goto :found

echo [ERROR] No usable virtualenv with required packages found.
echo   candidates checked: LQA_PY, .venv, E:\lqa_venv
echo   expected: a python that can `import fastapi`
echo   fix A: set LQA_PY to a python with the deps, e.g.
echo       set LQA_PY=E:\lqa_venv\Scripts\python.exe
echo   fix B: create it on an ASCII path and install deps
echo       "E:\python\python.exe" -m venv E:\lqa_venv
echo       E:\lqa_venv\Scripts\pip install -r requirements.txt
pause
exit /b 1

:found
echo Using interpreter: %PY%
"%PY%" -u api_server.py
if errorlevel 1 (
  echo.
  echo [ERROR] api_server.py exited with code %errorlevel%. See message above.
  pause
)
exit /b %errorlevel%

:probe_venv
rem arg1 = python path to test; returns 0 (success) if it can import fastapi
if "%~1"=="" exit /b 1
if not exist "%~1" exit /b 1
"%~1" -c "import fastapi" >nul 2>&1 || exit /b 1
set "PY=%~1"
exit /b 0
