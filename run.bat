@echo off
setlocal EnableDelayedExpansion

echo.
echo AI-Augmented Pandemic Response Model
echo ========================================
echo.

:: Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check for Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

:: Get script directory
set "SCRIPT_DIR=%~dp0"

:: Setup Backend
echo Setting up backend...
cd /d "%SCRIPT_DIR%backend"

if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies...
pip install -r requirements.txt --quiet

:: Setup Frontend
echo Setting up frontend...
cd /d "%SCRIPT_DIR%frontend"

if not exist "node_modules" (
    echo Installing Node.js dependencies...
    call npm install
)

:: Start servers
echo.
echo Starting servers...
echo.

:: Start backend in new window
cd /d "%SCRIPT_DIR%backend"
start "Pandemic Model - Backend" cmd /k "call venv\Scripts\activate.bat && uvicorn main:app --reload --port 8000"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in new window
cd /d "%SCRIPT_DIR%frontend"
start "Pandemic Model - Frontend" cmd /k "npm run dev"

:: Wait then open browser
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo Application is running!
echo.
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo Close the terminal windows to stop servers
echo ========================================
echo.

:: Open browser
start http://localhost:3000

pause
