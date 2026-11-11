@echo off
rem Thomas Transfer - start the dev server with one command.
rem Works from anywhere: always runs the project venv's Python in the repo root.
cd /d "%~dp0"

rem One server at a time: if something already listens on port 5000, do not
rem start a second instance (extra binds silently fail and leave zombies).
netstat -ano | findstr /r /c:":5000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo Thomas Transfer is already running at http://127.0.0.1:5000
    echo Close its window or press Ctrl+C there to stop it.
    pause
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo First run: creating the virtual environment and installing Flask...
    python -m venv .venv || goto :error
    ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || goto :error
)

echo Starting Thomas Transfer at http://127.0.0.1:5000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m backend.app
goto :eof

:error
echo Could not set up the virtual environment. Is Python installed and on PATH?
pause
exit /b 1
