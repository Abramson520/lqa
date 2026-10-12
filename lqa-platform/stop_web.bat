@echo off
rem Stop the LQA Web workbench bound to 127.0.0.1:8788 (ASCII-only to avoid GBK/UTF-8 mangling)
set "PORT=8788"
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
  set "FOUND=1"
  echo Killing PID %%p on port %PORT%
  taskkill /PID %%p /F >nul 2>&1
)
if "%FOUND%"=="0" (
  echo No process listening on port %PORT%.
) else (
  echo Port %PORT% released.
)
