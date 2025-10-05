#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_directories():
    """Create necessary directories"""
    directories = ['cache', 'logs', 'data']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"Created/verified directory: {directory}")

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import pandas
        logger.info("✅ All required packages are installed")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing required package: {e}")
        logger.error("Run: pip install -r requirements.txt")
        return False

def create_database():
    """Initialize database"""
    try:
        from api.database import engine, Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")

def start_server():
    """Start the FastAPI server"""
    try:
        logger.info("�� Starting SEIT Backend Server...")
        logger.info("📍 Server will be available at: http://localhost:8000")
        logger.info("📖 API Documentation: http://localhost:8000/docs")
        
        # Import and run
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    logger.info("🔧 Setting up SEIT Backend...")
    
    # Setup
    setup_directories()
    
    if not check_dependencies():
        sys.exit(1)
    
    create_database()
    
    # Start server
    start_server()
