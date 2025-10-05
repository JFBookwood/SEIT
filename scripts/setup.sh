#!/bin/bash

# SEIT - Automated Setup Script
set -e

echo "🌍 SEIT - Space Environmental Impact Tracker"
echo "============================================="
echo "This script will set up SEIT for development"
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required but not installed."
    echo "   Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is required but not installed."
    echo "   Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    echo "   Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

# Check pnpm
if ! command -v pnpm &> /dev/null; then
    echo "📦 Installing pnpm..."
    npm install -g pnpm
fi

echo "✅ All prerequisites satisfied"
echo ""

# Environment setup
echo "⚙️  Setting up environment..."

if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys before continuing"
    echo "   Required: SECRET_KEY, NASA_EARTHDATA_TOKEN"
    echo "   Optional: PURPLEAIR_API_KEY, OPENWEATHER_API_KEY"
    echo ""
    read -p "Press Enter after configuring .env file..."
fi

# Install dependencies
echo "📦 Installing dependencies..."

echo "   Installing frontend dependencies..."
pnpm install

echo "   Installing backend dependencies..."
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo "✅ Dependencies installed"
echo ""

# Database setup
echo "🗄️  Setting up database..."
cd backend
python -c "
from api.database import engine, Base
Base.metadata.create_all(bind=engine)
print('✅ Database initialized')
"
cd ..

# Docker setup
echo "�� Building Docker images..."
docker-compose build --no-cache

echo ""
echo "🎉 Setup complete!"
echo ""
echo "�� To start SEIT:"
echo "   Development: ./scripts/dev.sh"
echo "   Production:  docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend:    http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo ""
echo "📚 Next steps:"
echo "   1. Configure NASA Earthdata credentials in .env"
echo "   2. Add PurpleAir API key for live sensor data"
echo "   3. Start development server with ./scripts/dev.sh"
echo ""
