import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from ..models import SensorData

try:
    import tensorflow as tf
    from tensorflow.keras.models import Model
    from tensorflow.keras.layers import Input, Dense
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

class AnomalyService:
    """Service for detecting anomalies in environmental data"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def detect_anomalies(
        self,
        bbox: List[float],
        start_date: str,
        end_date: str,
        method: str = "isolation_forest",
        threshold: float = 0.1
    ) -> Dict[str, Any]:
        """Detect anomalies using specified method"""
        try:
            # Get sensor data
            sensor_data = self._get_sensor_data(bbox, start_date, end_date)
            
            if len(sensor_data) < 10:
                return {
                    "anomalies": [],
                    "summary": {
                        "total_records": len(sensor_data),
                        "anomalies_found": 0,
                        "message": "Insufficient data for anomaly detection"
                    }
                }
            
            # Detect anomalies based on method
            if method == "isolation_forest":
                anomalies = self._isolation_forest_detection(sensor_data, threshold)
            elif method == "autoencoder" and TENSORFLOW_AVAILABLE:
                anomalies = self._autoencoder_detection(sensor_data, threshold)
            elif method == "statistical":
                anomalies = self._statistical_detection(sensor_data, threshold)
            else:
                # Fallback to isolation forest
                anomalies = self._isolation_forest_detection(sensor_data, threshold)
            
            # Create GeoJSON features
            geojson_features = self._create_anomaly_features(anomalies, sensor_data)
            
            return {
                "anomalies": geojson_features,
                "summary": {
                    "total_records": len(sensor_data),
                    "anomalies_found": len(anomalies),
                    "anomaly_rate": len(anomalies) / len(sensor_data) * 100,
                    "method": method,
                    "threshold": threshold,
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            raise Exception(f"Anomaly detection failed: {str(e)}")
    
    def _get_sensor_data(self, bbox: List[float], start_date: str, end_date: str) -> pd.DataFrame:
        """Retrieve and filter sensor data for anomaly detection"""
        west, south, east, north = bbox
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        query = self.db.query(SensorData).filter(
            SensorData.longitude >= west,
            SensorData.longitude <= east,
            SensorData.latitude >= south,
            SensorData.latitude <= north,
            SensorData.timestamp >= start_dt,
            SensorData.timestamp <= end_dt
        )
        
        results = query.all()
        
        # Convert to DataFrame
        data = []
        for i, result in enumerate(results):
            data.append({
                'index': i,
                'sensor_id': result.sensor_id,
                'latitude': result.latitude,
                'longitude': result.longitude,
                'timestamp': result.timestamp,
                'pm25': result.pm25 if result.pm25 is not None else np.nan,
                'pm10': result.pm10 if result.pm10 is not None else np.nan,
                'temperature': result.temperature if result.temperature is not None else np.nan,
                'humidity': result.humidity if result.humidity is not None else np.nan,
                'pressure': result.pressure if result.pressure is not None else np.nan,
                'source': result.source
            })
        
        return pd.DataFrame(data)
    
    def _isolation_forest_detection(self, data: pd.DataFrame, contamination: float = 0.1) -> List[int]:
        """Detect anomalies using Isolation Forest"""
        # Select numeric columns for analysis
        feature_columns = ['pm25', 'pm10', 'temperature', 'humidity', 'pressure']
        available_columns = [col for col in feature_columns if col in data.columns]
        
        if not available_columns:
            return []
        
        # Prepare feature matrix
        feature_data = data[available_columns].copy()
        
        # Handle missing values
        feature_data = feature_data.fillna(feature_data.mean())
        
        # Remove rows where all values are NaN
        feature_data = feature_data.dropna(how='all')
        
        if len(feature_data) < 10:
            return []
        
        # Normalize features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(feature_data)
        
        # Fit Isolation Forest
        iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        
        # Predict anomalies (-1 for anomalies, 1 for normal)
        predictions = iso_forest.fit_predict(normalized_features)
        
        # Get anomaly scores
        anomaly_scores = iso_forest.score_samples(normalized_features)
        
        # Return indices of anomalies
        anomaly_indices = []
        for i, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
            if pred == -1:  # Anomaly
                original_index = feature_data.index[i]
                if original_index < len(data):
                    anomaly_indices.append(original_index)
        
        return anomaly_indices
    
    def _autoencoder_detection(self, data: pd.DataFrame, threshold: float = 0.1) -> List[int]:
        """Detect anomalies using autoencoder neural network"""
        if not TENSORFLOW_AVAILABLE:
            return self._isolation_forest_detection(data, threshold)
        
        # Select numeric columns
        feature_columns = ['pm25', 'pm10', 'temperature', 'humidity', 'pressure']
        available_columns = [col for col in feature_columns if col in data.columns]
        
        if not available_columns:
            return []
        
        # Prepare data
        feature_data = data[available_columns].copy()
        feature_data = feature_data.fillna(feature_data.mean())
        feature_data = feature_data.dropna(how='all')
        
        if len(feature_data) < 50:  # Need more data for neural network
            return self._isolation_forest_detection(data, threshold)
        
        # Normalize features
        scaler = StandardScaler()
        normalized_features = scaler.fit_transform(feature_data)
        
        # Build autoencoder
        input_dim = normalized_features.shape[1]
        encoding_dim = max(2, input_dim // 2)
        
        input_layer = Input(shape=(input_dim,))
        encoded = Dense(encoding_dim, activation='relu')(input_layer)
        decoded = Dense(input_dim, activation='linear')(encoded)
        
        autoencoder = Model(input_layer, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        
        # Train autoencoder
        autoencoder.fit(
            normalized_features, 
            normalized_features,
            epochs=50,
            batch_size=32,
            validation_split=0.1,
            verbose=0
        )
        
        # Calculate reconstruction error
        reconstructed = autoencoder.predict(normalized_features, verbose=0)
        mse = np.mean(np.square(normalized_features - reconstructed), axis=1)
        
        # Determine threshold (percentile-based)
        error_threshold = np.percentile(mse, (1 - threshold) * 100)
        
        # Find anomalies
        anomaly_indices = []
        for i, error in enumerate(mse):
            if error > error_threshold:
                original_index = feature_data.index[i]
                if original_index < len(data):
                    anomaly_indices.append(original_index)
        
        return anomaly_indices
    
    def _statistical_detection(self, data: pd.DataFrame, threshold: float = 0.05) -> List[int]:
        """Detect anomalies using statistical methods (Z-score and IQR)"""
        feature_columns = ['pm25', 'pm10', 'temperature', 'humidity', 'pressure']
        available_columns = [col for col in feature_columns if col in data.columns]
        
        if not available_columns:
            return []
        
        anomaly_indices = set()
        
        for column in available_columns:
            if column not in data.columns:
                continue
            
            series = data[column].dropna()
            if len(series) < 10:
                continue
            
            # Z-score method
            z_scores = np.abs((series - series.mean()) / series.std())
            z_threshold = 3  # 3 standard deviations
            z_anomalies = series[z_scores > z_threshold].index
            
            # IQR method
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            iqr_anomalies = series[(series < lower_bound) | (series > upper_bound)].index
            
            # Combine anomalies from both methods
            column_anomalies = set(z_anomalies) | set(iqr_anomalies)
            anomaly_indices.update(column_anomalies)
        
        return list(anomaly_indices)
    
    def _create_anomaly_features(self, anomaly_indices: List[int], data: pd.DataFrame) -> List[Dict]:
        """Create GeoJSON features for detected anomalies"""
        features = []
        
        for idx in anomaly_indices:
            if idx >= len(data):
                continue
            
            row = data.iloc[idx]
            
            # Calculate anomaly severity based on multiple factors
            severity_factors = []
            
            # PM2.5 severity
            if pd.notna(row.get('pm25')):
                pm25_value = row['pm25']
                if pm25_value > 55:  # Unhealthy
                    severity_factors.append(0.9)
                elif pm25_value > 35:  # Unhealthy for sensitive groups
                    severity_factors.append(0.7)
                elif pm25_value > 15:  # Moderate
                    severity_factors.append(0.5)
                else:
                    severity_factors.append(0.3)
            
            # Temperature anomaly severity
            if pd.notna(row.get('temperature')):
                temp_value = row['temperature']
                if temp_value > 40 or temp_value < -10:  # Extreme temperatures
                    severity_factors.append(0.8)
                elif temp_value > 35 or temp_value < 0:  # High/low temperatures
                    severity_factors.append(0.6)
                else:
                    severity_factors.append(0.4)
            
            # Overall severity score
            if severity_factors:
                severity_score = np.mean(severity_factors) * 100
            else:
                severity_score = 50  # Default moderate severity
            
            # Determine severity level and color
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
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row['longitude']), float(row['latitude'])]
                },
                "properties": {
                    "anomaly_id": f"anomaly_{idx}",
                    "sensor_id": row['sensor_id'],
                    "timestamp": row['timestamp'].isoformat() if pd.notna(row['timestamp']) else None,
                    "measurements": {
                        "pm25": float(row['pm25']) if pd.notna(row['pm25']) else None,
                        "pm10": float(row['pm10']) if pd.notna(row['pm10']) else None,
                        "temperature": float(row['temperature']) if pd.notna(row['temperature']) else None,
                        "humidity": float(row['humidity']) if pd.notna(row['humidity']) else None,
                        "pressure": float(row['pressure']) if pd.notna(row['pressure']) else None
                    },
                    "severity": {
                        "score": round(float(severity_score), 1),
                        "level": severity_level,
                        "color": color
                    },
                    "source": row['source'],
                    "anomaly_type": "environmental"
                }
            }
            
            features.append(feature)
        
        return features
