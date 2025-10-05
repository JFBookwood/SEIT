#!/bin/bash
echo "===================================" 
echo "    SEIT - Quick Start (Unix/Mac)"
echo "==================================="
echo
echo "This will start both backend and frontend"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo
read -p "Press Enter to continue..."

# Make scripts executable
chmod +x start-backend.sh
chmod +x start-frontend.sh

echo "1. Starting Backend..."
gnome-terminal -- bash -c "./start-backend.sh; exec bash" 2>/dev/null || \
terminal -- bash -c "./start-backend.sh; exec bash" 2>/dev/null || \
xterm -e "./start-backend.sh; exec bash" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "./start-backend.sh"' 2>/dev/null || \
echo "Please run './start-backend.sh' in a new terminal"

sleep 3

echo "2. Starting Frontend..."
gnome-terminal -- bash -c "./start-frontend.sh; exec bash" 2>/dev/null || \
terminal -- bash -c "./start-frontend.sh; exec bash" 2>/dev/null || \
xterm -e "./start-frontend.sh; exec bash" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "./start-frontend.sh"' 2>/dev/null || \
echo "Please run './start-frontend.sh' in a new terminal"

echo
echo "✅ Both services starting..."
echo "🌐 Open http://localhost:5173 in your browser"
echo "📖 API Docs: http://localhost:8000/docs"
echo
