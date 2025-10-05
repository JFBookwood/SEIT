import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import hashlib

from ..models.harmonized_models import ArtifactCache
from .redis_cache_service import cache_service

logger = logging.getLogger(__name__)

class SatelliteArtifactCache:
    """Specialized caching system for NASA satellite data artifacts"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
        # Cache TTL configurations for different products
        self.product_ttl = {
            'MOD04_L2': 86400,      # MODIS AOD: 24 hours
            'MYD04_L2': 86400,      # MODIS Aqua AOD: 24 hours
            'AIRS2RET': 43200,      # AIRS: 12 hours
            'ALIGNED_GRID': 21600,  # Aligned grids: 6 hours
            'PROCESSED_COVARIATE': 10800  # Processed covariates: 3 hours
        }
        
        # Storage configurations
        self.storage_config = {
            'max_artifact_size_mb': 50,
            'max_cache_age_days': 30,
            'compression_threshold_kb': 100
        }
    
    async def get_cached_satellite_data(
        self, 
        product_id: str, 
        date: str, 
        bbox: List[float],
        processing_params: Dict = None
    ) -> Optional[Dict]:
        """Retrieve cached satellite data artifact"""
        try:
            cache_key = self._generate_artifact_key(product_id, date, bbox, processing_params)
            
            # Try database cache first
            cached_artifact = self.db.query(ArtifactCache).filter(
                ArtifactCache.cache_key == cache_key,
                ArtifactCache.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if cached_artifact:
                logger.info(f"Satellite artifact cache hit: {cache_key}")
                return {
                    'product_id': product_id,
                    'date': date,
                    'bbox': bbox,
                    'grid_data': cached_artifact.grid_data,
                    'metadata': cached_artifact.metadata,
                    'cached_at': cached_artifact.created_at.isoformat(),
                    'cache_source': 'database'
                }
            
            # Try Redis cache as backup
            redis_data = await cache_service.get(cache_key, 'nasa_satellite')
            if redis_data:
                logger.info(f"Satellite artifact Redis cache hit: {cache_key}")
                return redis_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving cached satellite data: {e}")
            return None
    
    async def store_satellite_artifact(
        self,
        product_id: str,
        date: str,
        bbox: List[float],
        grid_data: Dict,
        processing_params: Dict = None,
        metadata: Dict = None
    ) -> bool:
        """Store satellite data artifact in cache"""
        try:
            cache_key = self._generate_artifact_key(product_id, date, bbox, processing_params)
            
            # Calculate expiration
            ttl_seconds = self.product_ttl.get(product_id, 21600)  # Default 6 hours
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            
            # Prepare metadata
            artifact_metadata = {
                'product_id': product_id,
                'processing_params': processing_params or {},
                'grid_cells': len(grid_data.get('grid_data', [])),
                'spatial_resolution_m': grid_data.get('spatial_resolution_m'),
                'alignment_method': grid_data.get('alignment_method'),
                'created_timestamp': datetime.now(timezone.utc).isoformat(),
                **(metadata or {})
            }
            
            # Calculate data size
            data_size_bytes = len(json.dumps(grid_data).encode('utf-8'))
            data_size_mb = data_size_bytes / (1024 * 1024)
            
            # Check size limits
            if data_size_mb > self.storage_config['max_artifact_size_mb']:
                logger.warning(f"Artifact too large for caching: {data_size_mb:.1f}MB > {self.storage_config['max_artifact_size_mb']}MB")
                return False
            
            # Store in database
            artifact = ArtifactCache(
                cache_key=cache_key,
                bbox=','.join(map(str, bbox)),
                timestamp_utc=datetime.fromisoformat(date),
                resolution=int(grid_data.get('spatial_resolution_m', 1000)),
                method=grid_data.get('alignment_method', 'unknown'),
                grid_data=grid_data,
                metadata=artifact_metadata,
                expires_at=expires_at,
                file_size_bytes=data_size_bytes,
                processing_time_ms=0  # Would be calculated in calling function
            )
            
            # Handle existing records
            existing = self.db.query(ArtifactCache).filter(
                ArtifactCache.cache_key == cache_key
            ).first()
            
            if existing:
                # Update existing artifact
                existing.grid_data = grid_data
                existing.metadata = artifact_metadata
                existing.expires_at = expires_at
                existing.file_size_bytes = data_size_bytes
            else:
                self.db.add(artifact)
            
            self.db.commit()
            
            # Also store in Redis for faster access
            await cache_service.set(
                cache_key,
                {
                    'product_id': product_id,
                    'date': date,
                    'bbox': bbox,
                    'grid_data': grid_data,
                    'metadata': artifact_metadata,
                    'cache_source': 'redis'
                },
                'nasa_satellite',
                custom_ttl=ttl_seconds
            )
            
            logger.info(f"Satellite artifact cached: {cache_key} ({data_size_mb:.1f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store satellite artifact: {e}")
            self.db.rollback()
            return False
    
    def _generate_artifact_key(
        self,
        product_id: str,
        date: str,
        bbox: List[float],
        processing_params: Dict = None
    ) -> str:
        """Generate unique cache key for satellite artifact"""
        # Create consistent key components
        key_components = [
            product_id,
            date,
            f"{bbox[0]:.3f}_{bbox[1]:.3f}_{bbox[2]:.3f}_{bbox[3]:.3f}",
        ]
        
        # Add processing parameters if provided
        if processing_params:
            params_str = json.dumps(processing_params, sort_keys=True)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
            key_components.append(params_hash)
        
        cache_key = "sat_" + "_".join(key_components)
        
        # Ensure key length is reasonable
        if len(cache_key) > 200:
            # Hash the entire key if too long
            cache_key = f"sat_{hashlib.md5(cache_key.encode()).hexdigest()}"
        
        return cache_key
    
    async def cleanup_expired_artifacts(self) -> Dict:
        """Clean up expired satellite artifacts"""
        try:
            cutoff_time = datetime.now(timezone.utc)
            
            # Find expired artifacts
            expired_artifacts = self.db.query(ArtifactCache).filter(
                ArtifactCache.expires_at <= cutoff_time
            ).all()
            
            # Calculate stats before deletion
            total_size_mb = sum(a.file_size_bytes for a in expired_artifacts) / (1024 * 1024)
            
            # Delete expired artifacts
            expired_count = len(expired_artifacts)
            for artifact in expired_artifacts:
                self.db.delete(artifact)
            
            self.db.commit()
            
            logger.info(f"Cleaned up {expired_count} expired satellite artifacts ({total_size_mb:.1f}MB)")
            
            return {
                'cleaned_artifacts': expired_count,
                'freed_space_mb': round(total_size_mb, 2),
                'cleanup_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Artifact cleanup failed: {e}")
            self.db.rollback()
            return {'error': str(e)}
    
    async def get_cache_statistics(self) -> Dict:
        """Get comprehensive cache statistics"""
        try:
            # Database cache stats
            total_artifacts = self.db.query(ArtifactCache).count()
            
            # Size statistics
            size_stats = self.db.query(
                self.db.func.sum(ArtifactCache.file_size_bytes),
                self.db.func.avg(ArtifactCache.file_size_bytes),
                self.db.func.max(ArtifactCache.file_size_bytes)
            ).first()
            
            total_size_bytes = size_stats[0] or 0
            avg_size_bytes = size_stats[1] or 0
            max_size_bytes = size_stats[2] or 0
            
            # Product breakdown
            product_stats = self.db.query(
                ArtifactCache.method,
                self.db.func.count(ArtifactCache.id)
            ).group_by(ArtifactCache.method).all()
            
            # Age analysis
            now = datetime.now(timezone.utc)
            age_stats = {
                'less_than_1_hour': 0,
                'less_than_6_hours': 0,
                'less_than_24_hours': 0,
                'older_than_24_hours': 0
            }
            
            artifacts = self.db.query(ArtifactCache).all()
            for artifact in artifacts:
                age_hours = (now - artifact.created_at).total_seconds() / 3600
                if age_hours < 1:
                    age_stats['less_than_1_hour'] += 1
                elif age_hours < 6:
                    age_stats['less_than_6_hours'] += 1
                elif age_hours < 24:
                    age_stats['less_than_24_hours'] += 1
                else:
                    age_stats['older_than_24_hours'] += 1
            
            return {
                'database_cache': {
                    'total_artifacts': total_artifacts,
                    'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
                    'average_size_kb': round(avg_size_bytes / 1024, 2),
                    'largest_artifact_mb': round(max_size_bytes / (1024 * 1024), 2)
                },
                'product_breakdown': dict(product_stats),
                'age_distribution': age_stats,
                'redis_cache': cache_service.get_cache_stats(),
                'statistics_timestamp': now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {'error': str(e)}

# Singleton instance
satellite_artifact_cache = SatelliteArtifactCache
