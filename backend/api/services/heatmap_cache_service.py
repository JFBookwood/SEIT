import hashlib
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.harmonized_models import ArtifactCache
from .redis_cache_service import cache_service

logger = logging.getLogger(__name__)

class HeatmapCacheService:
    """Specialized caching service for heatmap grid data and vector tiles"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
        # Cache TTL configurations
        self.cache_ttl = {
            'grid_data': 1800,      # 30 minutes for grid data
            'vector_tiles': 3600,   # 1 hour for vector tiles
            'snapshots': 7200,      # 2 hours for time snapshots
            'metadata': 86400       # 24 hours for metadata
        }
        
        # Grid resolution configurations
        self.resolution_configs = {
            100: {'max_bbox_area': 0.01, 'max_points': 5000},   # 100m - small areas only
            250: {'max_bbox_area': 0.1, 'max_points': 10000},   # 250m - default
            500: {'max_bbox_area': 0.5, 'max_points': 15000},   # 500m - large areas
            1000: {'max_bbox_area': 2.0, 'max_points': 20000}   # 1km - very large areas
        }
    
    async def get_cached_grid(self, bbox: List[float], resolution_m: int, 
                             timestamp: str = None, method: str = 'idw') -> Optional[Dict]:
        """Retrieve cached heatmap grid"""
        try:
            cache_key = self._generate_grid_cache_key(bbox, resolution_m, timestamp, method)
            
            # Try Redis cache first (faster)
            cached_data = await cache_service.get(cache_key, 'heatmap_tiles')
            if cached_data:
                logger.info(f"Heatmap grid cache hit (Redis): {cache_key}")
                return cached_data
            
            # Try database cache
            cached_artifact = self.db.query(ArtifactCache).filter(
                ArtifactCache.cache_key == cache_key,
                ArtifactCache.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if cached_artifact:
                logger.info(f"Heatmap grid cache hit (DB): {cache_key}")
                
                # Store back in Redis for faster access
                await cache_service.set(cache_key, cached_artifact.grid_data, 'heatmap_tiles')
                
                return cached_artifact.grid_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached grid: {e}")
            return None
    
    async def store_grid_cache(self, bbox: List[float], resolution_m: int, 
                              grid_data: Dict, processing_time_ms: float,
                              timestamp: str = None, method: str = 'idw') -> bool:
        """Store heatmap grid in cache"""
        try:
            cache_key = self._generate_grid_cache_key(bbox, resolution_m, timestamp, method)
            
            # Store in Redis
            await cache_service.set(cache_key, grid_data, 'heatmap_tiles', self.cache_ttl['grid_data'])
            
            # Store in database for persistence
            data_size_bytes = len(json.dumps(grid_data).encode('utf-8'))
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl['grid_data'])
            
            # Check if artifact already exists
            existing_artifact = self.db.query(ArtifactCache).filter(
                ArtifactCache.cache_key == cache_key
            ).first()
            
            if existing_artifact:
                # Update existing
                existing_artifact.grid_data = grid_data
                existing_artifact.expires_at = expires_at
                existing_artifact.processing_time_ms = int(processing_time_ms)
                existing_artifact.file_size_bytes = data_size_bytes
            else:
                # Create new artifact
                artifact = ArtifactCache(
                    cache_key=cache_key,
                    bbox=','.join(map(str, bbox)),
                    timestamp_utc=datetime.fromisoformat(timestamp) if timestamp else datetime.now(timezone.utc),
                    resolution=resolution_m,
                    method=method,
                    grid_data=grid_data,
                    metadata={
                        'grid_cells': len(grid_data.get('features', [])),
                        'interpolation_method': method,
                        'processing_time_ms': processing_time_ms
                    },
                    expires_at=expires_at,
                    file_size_bytes=data_size_bytes,
                    processing_time_ms=int(processing_time_ms)
                )
                self.db.add(artifact)
            
            self.db.commit()
            
            logger.info(f"Heatmap grid cached: {cache_key} ({data_size_bytes/1024:.1f}KB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache grid data: {e}")
            self.db.rollback()
            return False
    
    async def get_cached_vector_tile(self, z: int, x: int, y: int, 
                                   timestamp: str = None, method: str = 'idw') -> Optional[bytes]:
        """Retrieve cached vector tile"""
        try:
            cache_key = f"vt_{method}_{z}_{x}_{y}_{timestamp or 'latest'}"
            
            cached_tile = await cache_service.get(cache_key, 'vector_tiles')
            if cached_tile:
                logger.debug(f"Vector tile cache hit: {cache_key}")
                return cached_tile
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached vector tile: {e}")
            return None
    
    async def store_vector_tile(self, z: int, x: int, y: int, tile_data: bytes,
                               timestamp: str = None, method: str = 'idw') -> bool:
        """Store vector tile in cache"""
        try:
            cache_key = f"vt_{method}_{z}_{x}_{y}_{timestamp or 'latest'}"
            
            await cache_service.set(cache_key, tile_data, 'vector_tiles', self.cache_ttl['vector_tiles'])
            
            logger.debug(f"Vector tile cached: {cache_key} ({len(tile_data)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache vector tile: {e}")
            return False
    
    def _generate_grid_cache_key(self, bbox: List[float], resolution_m: int,
                                timestamp: str = None, method: str = 'idw') -> str:
        """Generate cache key for grid data"""
        bbox_str = '_'.join(f"{coord:.4f}" for coord in bbox)
        timestamp_str = timestamp or 'latest'
        
        key_components = [
            'heatmap',
            method,
            f"res{resolution_m}",
            f"bbox{bbox_str}",
            f"t{timestamp_str}"
        ]
        
        cache_key = '_'.join(key_components)
        
        # Hash if too long
        if len(cache_key) > 200:
            cache_key = f"heatmap_{hashlib.md5(cache_key.encode()).hexdigest()}"
        
        return cache_key
    
    def _filter_features_by_bounds(self, features: List[Dict], bounds: List[float]) -> List[Dict]:
        """Filter features within bounds"""
        west, south, east, north = bounds
        filtered = []
        
        for feature in features:
            coords = feature['geometry']['coordinates']
            lon, lat = coords[0], coords[1]
            
            if west <= lon <= east and south <= lat <= north:
                filtered.append(feature)
        
        return filtered
    
    def validate_grid_resolution(self, bbox: List[float], resolution_m: int) -> Dict[str, Any]:
        """Validate grid resolution is appropriate for bbox size"""
        west, south, east, north = bbox
        
        # Calculate bbox area (approximate)
        width_deg = east - west
        height_deg = north - south
        area_deg2 = width_deg * height_deg
        
        # Get resolution limits
        config = self.resolution_configs.get(resolution_m)
        if not config:
            return {
                'valid': False,
                'error': f'Unsupported resolution: {resolution_m}m',
                'supported_resolutions': list(self.resolution_configs.keys())
            }
        
        # Check area limits
        if area_deg2 > config['max_bbox_area']:
            return {
                'valid': False,
                'error': f'Bbox too large for {resolution_m}m resolution',
                'max_area_deg2': config['max_bbox_area'],
                'current_area_deg2': area_deg2,
                'suggested_resolution': self._suggest_resolution(area_deg2)
            }
        
        # Estimate grid size
        resolution_deg = resolution_m / 111320
        estimated_points = (width_deg / resolution_deg) * (height_deg / resolution_deg)
        
        if estimated_points > config['max_points']:
            return {
                'valid': False,
                'error': f'Too many grid points for {resolution_m}m resolution',
                'estimated_points': int(estimated_points),
                'max_points': config['max_points'],
                'suggested_resolution': self._suggest_resolution(area_deg2)
            }
        
        return {
            'valid': True,
            'estimated_points': int(estimated_points),
            'estimated_size_mb': estimated_points * 0.001,  # Rough estimate
            'processing_time_estimate_seconds': estimated_points / 1000
        }
    
    def _suggest_resolution(self, area_deg2: float) -> int:
        """Suggest appropriate resolution for given area"""
        if area_deg2 <= 0.01:
            return 100
        elif area_deg2 <= 0.1:
            return 250
        elif area_deg2 <= 0.5:
            return 500
        else:
            return 1000
    
    async def cleanup_expired_cache(self) -> Dict:
        """Clean up expired heatmap cache entries"""
        try:
            cutoff_time = datetime.now(timezone.utc)
            
            # Clean database cache
            expired_artifacts = self.db.query(ArtifactCache).filter(
                ArtifactCache.expires_at <= cutoff_time,
                ArtifactCache.cache_key.like('heatmap%')
            ).all()
            
            db_cleaned = len(expired_artifacts)
            db_size_mb = sum(a.file_size_bytes for a in expired_artifacts) / (1024 * 1024)
            
            for artifact in expired_artifacts:
                self.db.delete(artifact)
            
            self.db.commit()
            
            # Clean Redis cache
            redis_cleaned = await cache_service.clear_pattern("heatmap*")
            
            return {
                'database_entries_cleaned': db_cleaned,
                'database_size_freed_mb': round(db_size_mb, 2),
                'redis_entries_cleaned': redis_cleaned,
                'cleanup_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            self.db.rollback()
            return {'error': str(e)}

# Singleton factory function
def create_heatmap_cache_service(db_session: Session) -> HeatmapCacheService:
    return HeatmapCacheService(db_session)
