#!/bin/bash

# SEIT Production Deployment Script
set -e

echo "🚀 SEIT Production Deployment"
echo "============================="

# Configuration
COMPOSE_FILE=${1:-docker-compose.prod.yml}
ENVIRONMENT=${2:-production}

echo "📋 Configuration:"
echo "   Compose file: $COMPOSE_FILE"
echo "   Environment:  $ENVIRONMENT"
echo ""

# Pre-deployment checks
echo "🔍 Pre-deployment checks..."

# Check .env file
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy .env.example to .env and configure"
    exit 1
fi

# Check required environment variables
required_vars=("SECRET_KEY" "NASA_EARTHDATA_TOKEN")
for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=$" .env; then
        echo "❌ Required environment variable $var not configured"
        exit 1
    fi
done

echo "✅ Environment configuration valid"

# Check Docker
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

echo "✅ Docker is running"

# Build and deploy
echo ""
echo "🔨 Building application..."
docker-compose -f $COMPOSE_FILE build --no-cache

echo "�� Starting services..."
docker-compose -f $COMPOSE_FILE up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Health checks
echo "🏥 Running health checks..."

# Check backend health
if curl -f http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "✅ Backend health check passed"
else
    echo "❌ Backend health check failed"
    docker-compose -f $COMPOSE_FILE logs backend
    exit 1
fi

# Check frontend
if curl -f http://localhost:3000/ >/dev/null 2>&1; then
    echo "✅ Frontend health check passed"
else
    echo "❌ Frontend health check failed"
    docker-compose -f $COMPOSE_FILE logs frontend
    exit 1
fi

# Check database connection
if docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U seit_user -d seit_db >/dev/null 2>&1; then
    echo "✅ Database health check passed"
else
    echo "❌ Database health check failed"
    docker-compose -f $COMPOSE_FILE logs postgres
    exit 1
fi

echo ""
echo "🎉 Deployment Successful!"
echo "========================"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend:    http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo ""
echo "🔧 Management Commands:"
echo "   View logs:   docker-compose -f $COMPOSE_FILE logs -f"
echo "   Stop:        docker-compose -f $COMPOSE_FILE down"
echo "   Restart:     docker-compose -f $COMPOSE_FILE restart"
echo "   Update:      git pull && ./scripts/deploy.sh"
echo ""
echo "📊 Monitoring:"
echo "   Health:      curl http://localhost:8000/api/health"
echo "   Status:      curl http://localhost:8000/api/admin/status"
echo "   Database:    docker-compose -f $COMPOSE_FILE exec postgres psql -U seit_user -d seit_db"
echo ""

# Show running containers
echo "🐳 Running containers:"
docker-compose -f $COMPOSE_FILE ps

echo ""
echo "✅ SEIT is now running in $ENVIRONMENT mode!"
