from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..database import get_db
from ..services.enhanced_async_integration_service import EnhancedAsyncIntegrationService
from ..services.redis_cache_service import cache_service
from ..services.rate_limiter import rate_limit_manager

router = APIRouter()

@router.get("/async-integration/comprehensive")
async def get_comprehensive_async_data(
    bbox: Optional[str] = None,
    include_satellite: bool = True,
    include_weather: bool = True,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get comprehensive environmental data with async fetching and caching"""
    try:
        integration_service = EnhancedAsyncIntegrationService(db)
        
        data = await integration_service.get_comprehensive_data(
            bbox=bbox,
            include_satellite=include_satellite,
            include_weather=include_weather,
            date=date
        )
        
        return data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Async integration failed: {str(e)}")

@router.get("/async-integration/statistics")
async def get_integration_statistics(db: Session = Depends(get_db)):
    """Get detailed statistics about async integration performance"""
    try:
        integration_service = EnhancedAsyncIntegrationService(db)
        stats = await integration_service.get_integration_statistics()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")

@router.post("/async-integration/refresh-cache")
async def refresh_integration_cache(
    bbox: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Refresh cached data for better performance"""
    try:
        integration_service = EnhancedAsyncIntegrationService(db)
        
        if bbox:
            # Clear cache for specific region
            cleared_count = await integration_service.clear_cache_for_bbox(bbox)
            # Pre-fetch fresh data
            fresh_data = await integration_service.get_comprehensive_data(bbox, True, True)
            
            return {
                "message": f"Cache refreshed for bbox: {bbox}",
                "cleared_entries": cleared_count,
                "fresh_sensors": fresh_data['statistics']['total'],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Refresh all caches
            if background_tasks:
                background_tasks.add_task(integration_service.refresh_all_caches)
                return {
                    "message": "Global cache refresh started in background",
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                result = await integration_service.refresh_all_caches()
                return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache refresh failed: {str(e)}")

@router.get("/async-integration/rate-limits")
async def get_rate_limit_status():
    """Get current rate limiting status for all services"""
    try:
        status = rate_limit_manager.get_all_status()
        return {
            "rate_limits": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving rate limit status: {str(e)}")

@router.post("/async-integration/clear-cache")
async def clear_integration_cache(
    pattern: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Clear cached data with optional pattern matching"""
    try:
        if pattern:
            cleared_count = await cache_service.clear_pattern(pattern)
        else:
            cleared_count = await cache_service.clear_pattern("*")
        
        return {
            "message": f"Cleared {cleared_count} cache entries",
            "pattern": pattern or "all",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clearing failed: {str(e)}")

@router.get("/async-integration/cache-stats")
async def get_cache_statistics():
    """Get detailed cache performance statistics"""
    try:
        stats = cache_service.get_cache_stats()
        return {
            "cache_statistics": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving cache stats: {str(e)}")
