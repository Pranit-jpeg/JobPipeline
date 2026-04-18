@echo off
REM ============================================================
REM  JobPipeline — One-click daily run (Windows)
REM  - Activates the venv
REM  - Runs the full daily pipeline (scrape, score, cleanup, H1B)
REM  - Starts the dashboard API in a new window
REM  - Opens the dashboard in your default browser
REM ============================================================

setlocal
cd /d "%~dp0"

REM --- Sanity check: venv must exist --------------------------
if not exist "venv\Scripts\python.exe" (
  echo.
  echo [run.bat] ERROR: venv not found at venv\Scripts\python.exe
  echo          Create it first:  python -m venv venv
  echo                            venv\Scripts\pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM --- Phase 1: scrape + score + cleanup + h1b ---------------
echo.
echo ============================================================
echo  JobPipeline — Daily Run
echo ============================================================
echo.
"venv\Scripts\python.exe" daily_run.py
if errorlevel 1 (
  echo.
  echo [run.bat] daily_run.py exited with an error. See logs\ for details.
  pause
  exit /b 1
)

REM --- Phase 2: launch dashboard API in a new window ---------
echo.
echo Starting dashboard API on http://localhost:5000 ...
start "JobPipeline API" "venv\Scripts\python.exe" dashboard\api.py

REM --- Phase 3: wait a couple seconds, then open browser -----
timeout /t 3 /nobreak >nul
start "" "dashboard\index.html"

echo.
echo Dashboard is running. Close this window to leave it running in the background.
echo Close the "JobPipeline API" window to stop the API server.
echo.
pause
endlocal
