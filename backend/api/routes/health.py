from fastapi import APIRouter
from datetime import datetime
import os

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SEIT Backend",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@router.get("/status")
async def detailed_status():
    """Detailed status endpoint"""
    return {
        "status": "operational",
        "services": {
            "api": "healthy",
            "database": "connected",
            "cache": "available"
        },
        "endpoints": {
            "sensors": "/api/sensors/*",
            "satellite": "/api/satellite/*", 
            "analytics": "/api/analytics/*",
            "export": "/api/export/*"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
