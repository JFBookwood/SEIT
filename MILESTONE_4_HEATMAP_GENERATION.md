# MILESTONE 4: PM2.5 Heatmap Generation

## 🎯 OBJECTIVE
Implement scientifically sound spatial interpolation with uncertainty quantification.

## 📋 IMPLEMENTATION TASKS

### Task 4.1: IDW Baseline Implementation
**Time: 75 minutes**

#### Fast IDW Algorithm
```python
class IDWInterpolationService:
    def __init__(self, power: float = 2.0, search_radius: float = 5000):
        self.power = power
        self.search_radius = search_radius  # meters
    
    def interpolate_grid(self, sensors: List[dict], grid_bounds: List[float], 
                        resolution: float = 250) -> np.ndarray:
        """
        Generate IDW interpolation grid with uncertainty
        
        Returns:
            grid: shape (ny, nx, 4) with [c_hat, uncertainty, n_eff, timestamp]
        """
        
        # Create spatial grid
        west, south, east, north = grid_bounds
        x = np.arange(west, east, resolution/111320)  # ~250m in degrees
        y = np.arange(south, north, resolution/111320)
        
        grid = np.full((len(y), len(x), 4), np.nan)
        
        for i, lat in enumerate(y):
            for j, lon in enumerate(x):
                result = self.interpolate_point(lon, lat, sensors)
                if result:
                    grid[i, j, :] = result
        
        return grid
    
    def interpolate_point(self, lon: float, lat: float, sensors: List[dict]):
        """IDW interpolation for single point"""
        weights = []
        values = []
        uncertainties = []
        
        for sensor in sensors:
            distance = self.haversine_distance(lat, lon, sensor['lat'], sensor['lon'])
            if distance <= self.search_radius:
                weight = 1 / (distance + 1) ** self.power  # +1 to avoid division by zero
                
                # Use calibration uncertainty as additional weight
                calib_weight = 1 / (sensor.get('sigma_i', 1.0) ** 2)
                final_weight = weight * calib_weight
                
                weights.append(final_weight)
                values.append(sensor['pm25_corrected'])
                uncertainties.append(sensor.get('sigma_i', 1.0))
        
        if not weights:
            return None
        
        weights = np.array(weights)
        values = np.array(values)
        
        # Weighted interpolation
        c_hat = np.sum(weights * values) / np.sum(weights)
        uncertainty = 1 / np.sqrt(np.sum(weights))  # Inverse variance weighting
        n_eff = len(weights)
        timestamp = datetime.utcnow().timestamp()
        
        return [c_hat, uncertainty, n_eff, timestamp]
```

### Task 4.2: Research-Grade Kriging
**Time: 90 minutes**

#### Universal Kriging Implementation
```python
class KrigingInterpolationService:
    def __init__(self):
        self.variogram_models = ['spherical', 'exponential', 'gaussian']
    
    def fit_kriging_model(self, sensors: List[dict], covariates: dict):
        """Fit universal kriging with external drift"""
        
        # Prepare data matrices
        coordinates = np.array([[s['lat'], s['lon']] for s in sensors])
        observations = np.array([s['pm25_corrected'] for s in sensors])
        
        # External drift covariates (NASA data, meteorology)
        drift_matrix = self.prepare_drift_matrix(sensors, covariates)
        
        # Fit kriging model
        from pykrige import UniversalKriging
        
        uk = UniversalKriging(
            coordinates[:, 1],  # longitude
            coordinates[:, 0],  # latitude
            observations,
            variogram_model='exponential',
            drift_terms=drift_matrix,
            verbose=False,
            enable_plotting=False
        )
        
        return uk
    
    def generate_kriging_grid(self, uk_model, grid_bounds: List[float], 
                             resolution: float = 250):
        """Generate kriging interpolation with uncertainty"""
        
        west, south, east, north = grid_bounds
        
        # Create grid coordinates
        grid_lon = np.arange(west, east, resolution/111320)
        grid_lat = np.arange(south, north, resolution/111320)
        
        # Perform kriging
        c_hat, kriging_variance = uk_model.execute(
            'grid', grid_lon, grid_lat, backend='loop'
        )
        
        # Calculate uncertainty from kriging variance
        uncertainty = np.sqrt(kriging_variance)
        
        return c_hat, uncertainty
```

### Task 4.3: Tile Service Architecture
**Time: 60 minutes**

#### Vector Tile Generation
```python
class HeatmapTileService:
    async def generate_vector_tile(self, z: int, x: int, y: int, 
                                 timestamp: str, method: str = 'idw'):
        """Generate vector tile for heatmap layer"""
        
        # Calculate tile bounds
        bounds = self.tile_to_bbox(z, x, y)
        
        # Get cached grid or generate new one
        grid_data = await self.get_or_generate_grid(bounds, timestamp, method)
        
        # Convert to vector tile format
        features = self.grid_to_features(grid_data)
        
        return self.encode_vector_tile(features)
    
    def grid_to_features(self, grid_data: np.ndarray):
        """Convert interpolation grid to GeoJSON features"""
        features = []
        
        for i in range(grid_data.shape[0]):
            for j in range(grid_data.shape[1]):
                c_hat, uncertainty, n_eff, timestamp = grid_data[i, j, :]
                
                if not np.isnan(c_hat):
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]  # Calculate from grid indices
                        },
                        "properties": {
                            "c_hat": float(c_hat),
                            "uncertainty": float(uncertainty),
                            "n_eff": int(n_eff),
                            "timestamp_utc": timestamp,
                            "color": self.get_pm25_color(c_hat),
                            "opacity": self.get_uncertainty_opacity(uncertainty)
                        }
                    }
                    features.append(feature)
        
        return features
```

#### API Endpoint Design
```python
@router.get("/heatmap/tiles")
async def get_heatmap_tile(z: int, x: int, y: int, t: str, method: str = "idw"):
    """Return heatmap vector tile"""
    
@router.get("/heatmap/grid")
async def get_heatmap_grid(minlat: float, minlon: float, maxlat: float, 
                          maxlon: float, res: float = 250, t: str = None):
    """Return GeoJSON grid with interpolated values"""
```

## 🔬 SCIENTIFIC VALIDATION

### Interpolation Methods
1. **IDW Baseline**: Fast, reliable, well-understood method
2. **Universal Kriging**: Optimal linear predictor with uncertainty
3. **Gaussian Process**: Advanced ML approach with covariate learning

### Uncertainty Quantification
- **IDW**: Inverse variance weighting uncertainty
- **Kriging**: True kriging variance from semivariogram
- **Calibration**: Propagate per-sensor uncertainty (sigma_i)

### Grid Quality Metrics
- Ensure no NaN values in valid areas
- Validate c_hat within reasonable ranges (0-500 μg/m³)
- Check uncertainty estimates are meaningful
- Verify temporal consistency of snapshots

## ✅ ACCEPTANCE CRITERIA

### Algorithm Implementation
- [ ] IDW interpolation producing valid grids
- [ ] Kriging model fitting and prediction working
- [ ] Uncertainty estimates calculated correctly
- [ ] Grid resolution configurable (100-1000m)

### API Performance
- [ ] Tile endpoints responding within 2 seconds
- [ ] Grid endpoints handling large bboxes efficiently
- [ ] Caching reducing repeated computation
- [ ] Vector tiles optimized for frontend rendering

### Scientific Accuracy
- [ ] Cross-validation showing reasonable RMSE/MAE
- [ ] Uncertainty estimates correlating with prediction quality
- [ ] Spatial patterns visually coherent and interpretable
- [ ] Temporal snapshots showing realistic evolution
