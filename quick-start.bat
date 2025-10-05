@echo off
echo ===================================
echo    SEIT - Quick Start (Windows)
echo ===================================
echo.
echo This will start both backend and frontend
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause

echo 1. Starting Backend...
start "SEIT Backend" cmd /k "cd backend && python startup.py"
timeout /t 3 >nul

echo 2. Starting Frontend...
start "SEIT Frontend" cmd /k "pnpm dev"

echo.
echo ✅ Both services starting...
echo 🌐 Open http://localhost:5173 in your browser
echo 📖 API Docs: http://localhost:8000/docs
echo.
pause
