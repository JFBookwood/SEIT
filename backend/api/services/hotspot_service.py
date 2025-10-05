import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple, Any
from datetime import datetime
import json
from ..models import SensorData

class HotspotService:
    """Service for detecting environmental hotspots using clustering algorithms"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def detect_hotspots(
        self,
        bbox: List[float],
        start_date: str,
        end_date: str,
        grid_size: float = 0.01,  # ~1km at equator
        eps: float = 0.01,
        min_samples: int = 3
    ) -> Dict[str, Any]:
        """Detect environmental hotspots using DBSCAN clustering"""
        try:
            # Get sensor data
            sensor_data = self._get_sensor_data(bbox, start_date, end_date)
            
            if len(sensor_data) < min_samples:
                return {
                    "hotspots": [],
                    "summary": {
                        "total_sensors": len(sensor_data),
                        "hotspots_found": 0,
                        "message": "Insufficient data for hotspot analysis"
                    }
                }
            
            # Create spatial grid
            grid_data = self._create_spatial_grid(sensor_data, grid_size)
            
            if len(grid_data) < min_samples:
                return {
                    "hotspots": [],
                    "summary": {
                        "total_sensors": len(sensor_data),
                        "grid_cells": len(grid_data),
                        "hotspots_found": 0,
                        "message": "Insufficient grid cells for clustering"
                    }
                }
            
            # Perform clustering
            hotspots = self._perform_clustering(grid_data, eps, min_samples)
            
            # Calculate severity scores
            hotspots_with_severity = self._calculate_severity(hotspots, sensor_data)
            
            # Generate GeoJSON features
            geojson_features = self._create_geojson_features(hotspots_with_severity)
            
            return {
                "hotspots": geojson_features,
                "summary": {
                    "total_sensors": len(sensor_data),
                    "grid_cells": len(grid_data),
                    "hotspots_found": len(hotspots_with_severity),
                    "parameters": {
                        "grid_size": grid_size,
                        "eps": eps,
                        "min_samples": min_samples
                    },
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            raise Exception(f"Hotspot detection failed: {str(e)}")
    
    def _get_sensor_data(self, bbox: List[float], start_date: str, end_date: str) -> pd.DataFrame:
        """Retrieve and filter sensor data"""
        west, south, east, north = bbox
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        query = self.db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start_dt,
            SensorData.timestamp <= end_dt,
            SensorData.pm25.isnot(None)  # Ensure we have PM2.5 data
        )
        
        results = query.all()
        
        # Convert to DataFrame
        data = []
        for result in results:
            data.append({
                'sensor_id': result.sensor_id,
                'latitude': result.latitude,
                'longitude': result.longitude,
                'timestamp': result.timestamp,
                'pm25': result.pm25,
                'pm10': result.pm10,
                'temperature': result.temperature,
                'humidity': result.humidity,
                'source': result.source
            })
        
        return pd.DataFrame(data)
    
    def _create_spatial_grid(self, data: pd.DataFrame, grid_size: float) -> pd.DataFrame:
        """Create spatial grid and aggregate sensor data"""
        if data.empty:
            return pd.DataFrame()
        
        # Create grid coordinates
        data['grid_lat'] = (data['latitude'] // grid_size) * grid_size + grid_size / 2
        data['grid_lng'] = (data['longitude'] // grid_size) * grid_size + grid_size / 2
        
        # Aggregate by grid cell
        aggregated = data.groupby(['grid_lat', 'grid_lng']).agg({
            'pm25': ['mean', 'max', 'std', 'count'],
            'pm10': ['mean', 'max', 'std'],
            'temperature': ['mean'],
            'humidity': ['mean'],
            'sensor_id': 'nunique'
        }).reset_index()
        
        # Flatten column names
        aggregated.columns = [
            'latitude', 'longitude', 
            'pm25_mean', 'pm25_max', 'pm25_std', 'pm25_count',
            'pm10_mean', 'pm10_max', 'pm10_std',
            'temp_mean', 'humidity_mean', 'sensor_count'
        ]
        
        # Fill NaN values
        aggregated = aggregated.fillna(0)
        
        return aggregated
    
    def _perform_clustering(
        self, 
        grid_data: pd.DataFrame, 
        eps: float, 
        min_samples: int
    ) -> List[Dict]:
        """Perform DBSCAN clustering on grid data"""
        if len(grid_data) < min_samples:
            return []
        
        # Prepare features for clustering
        features = []
        feature_columns = ['latitude', 'longitude', 'pm25_mean', 'pm25_max']
        
        # Only use available columns
        available_columns = [col for col in feature_columns if col in grid_data.columns]
        feature_matrix = grid_data[available_columns].values
        
        # Normalize features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(feature_matrix)
        
        # Perform clustering
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        cluster_labels = dbscan.fit_predict(normalized_features)
        
        # Extract hotspot clusters (excluding noise points with label -1)
        hotspots = []
        unique_labels = set(cluster_labels)
        
        for label in unique_labels:
            if label == -1:  # Skip noise points
                continue
            
            # Get points in this cluster
            cluster_mask = cluster_labels == label
            cluster_points = grid_data[cluster_mask]
            
            if len(cluster_points) >= min_samples:
                hotspot = {
                    'cluster_id': int(label),
                    'points': cluster_points.to_dict('records'),
                    'centroid': {
                        'latitude': float(cluster_points['latitude'].mean()),
                        'longitude': float(cluster_points['longitude'].mean())
                    },
                    'size': len(cluster_points),
                    'bounds': {
                        'north': float(cluster_points['latitude'].max()),
                        'south': float(cluster_points['latitude'].min()),
                        'east': float(cluster_points['longitude'].max()),
                        'west': float(cluster_points['longitude'].min())
                    }
                }
                hotspots.append(hotspot)
        
        return hotspots
    
    def _calculate_severity(self, hotspots: List[Dict], sensor_data: pd.DataFrame) -> List[Dict]:
        """Calculate severity scores for hotspots"""
        if sensor_data.empty:
            overall_mean = 25.0  # Default PM2.5 baseline
            overall_std = 15.0
        else:
            overall_mean = sensor_data['pm25'].mean()
            overall_std = sensor_data['pm25'].std()
        
        for hotspot in hotspots:
            points = pd.DataFrame(hotspot['points'])
            
            if not points.empty and 'pm25_mean' in points.columns:
                # Calculate various severity metrics
                max_pm25 = points['pm25_mean'].max()
                mean_pm25 = points['pm25_mean'].mean()
                
                # Severity based on deviation from overall mean
                severity_score = min(100, max(0, (mean_pm25 - overall_mean) / overall_std * 25 + 50))
                
                # Classification
                if severity_score >= 80:
                    severity_level = "critical"
                    color = "#dc2626"  # red
                elif severity_score >= 60:
                    severity_level = "high"
                    color = "#ea580c"  # orange
                elif severity_score >= 40:
                    severity_level = "moderate"
                    color = "#ca8a04"  # yellow
                else:
                    severity_level = "low"
                    color = "#16a34a"  # green
            else:
                severity_score = 50
                severity_level = "unknown"
                color = "#6b7280"  # gray
                mean_pm25 = 0
                max_pm25 = 0
            
            hotspot.update({
                'severity': {
                    'score': round(float(severity_score), 1),
                    'level': severity_level,
                    'color': color,
                    'pm25_mean': round(float(mean_pm25), 2),
                    'pm25_max': round(float(max_pm25), 2)
                }
            })
        
        return hotspots
    
    def _create_geojson_features(self, hotspots: List[Dict]) -> List[Dict]:
        """Convert hotspots to GeoJSON features"""
        features = []
        
        for hotspot in hotspots:
            # Create polygon from bounds
            bounds = hotspot['bounds']
            coordinates = [[
                [bounds['west'], bounds['north']],
                [bounds['east'], bounds['north']],
                [bounds['east'], bounds['south']],
                [bounds['west'], bounds['south']],
                [bounds['west'], bounds['north']]
            ]]
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coordinates
                },
                "properties": {
                    "cluster_id": hotspot['cluster_id'],
                    "centroid": hotspot['centroid'],
                    "size": hotspot['size'],
                    "severity": hotspot['severity'],
                    "grid_points": len(hotspot['points']),
                    "hotspot_type": "environmental"
                }
            }
            
            features.append(feature)
        
        return features
