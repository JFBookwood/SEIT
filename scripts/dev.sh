#!/bin/bash

# SEIT Development Server Startup
set -e

echo "🚀 Starting SEIT Development Environment"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Run ./scripts/setup.sh first"
    exit 1
fi

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Check ports
if check_port 8000; then
    echo "⚠️  Port 8000 is already in use (backend)"
    echo "   Kill existing process or change PORT in .env"
fi

if check_port 3000; then
    echo "⚠️  Port 3000 is already in use (frontend)"
    echo "   Kill existing process or change FRONTEND_PORT in .env"
fi

# Start backend
echo "�� Starting backend server..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Test backend health
if curl -f http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "✅ Backend server healthy"
else
    echo "❌ Backend server failed to start"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Start frontend
echo "🎨 Starting frontend development server..."
pnpm dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 10

echo ""
echo "🎉 SEIT Development Environment Ready!"
echo "======================================"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend:    http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo ""
echo "🔧 Development Commands:"
echo "   Stop servers: Ctrl+C"
echo "   View logs:    tail -f backend/logs/application.log"
echo "   Test APIs:    curl http://localhost:8000/api/health"
echo ""
echo "📊 Monitoring:"
echo "   Backend PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "�� Stopping SEIT development servers..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "✅ Servers stopped"
    exit 0
}

# Trap signals for cleanup
trap cleanup SIGINT SIGTERM

# Keep script running
wait
