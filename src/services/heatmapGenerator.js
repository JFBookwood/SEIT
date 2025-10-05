// Heatmap generation service for PM2.5 spatial interpolation
import { calculateDistance } from './geoUtils';

/**
 * Generate PM2.5 heatmap using IDW interpolation
 */
export function generateHeatmapGrid(sensorData, bounds, options = {}) {
  const {
    resolution = 250,
    method = 'idw',
    searchRadius = 5000,
    power = 2
  } = options;

  if (!sensorData.length || !bounds) {
    return [];
  }

  const [west, south, east, north] = bounds;
  
  // Calculate grid step in degrees (approximate)
  const stepDegrees = resolution / 111320; // Convert meters to degrees
  
  // Generate grid points
  const gridPoints = [];
  
  for (let lat = south; lat <= north; lat += stepDegrees) {
    for (let lon = west; lon <= east; lon += stepDegrees) {
      const interpolatedPoint = interpolatePoint(lon, lat, sensorData, {
        searchRadius,
        power,
        method
      });
      
      if (interpolatedPoint) {
        gridPoints.push({
          lat,
          lon,
          ...interpolatedPoint
        });
      }
    }
  }
  
  return gridPoints;
}

/**
 * Interpolate PM2.5 value at specific point using IDW
 */
function interpolatePoint(lon, lat, sensors, options) {
  const { searchRadius, power } = options;
  
  const weights = [];
  const values = [];
  const uncertainties = [];
  
  // Find sensors within search radius
  for (const sensor of sensors) {
    if (!sensor.latitude || !sensor.longitude || !sensor.pm25) continue;
    
    const distance = calculateDistance(
      lat, lon,
      sensor.latitude, sensor.longitude
    );
    
    if (distance <= searchRadius) {
      // IDW weight calculation
      const weight = distance === 0 ? 1e10 : 1 / Math.pow(distance, power);
      
      weights.push(weight);
      values.push(parseFloat(sensor.pm25));
      uncertainties.push(sensor.sigma_i || 5.0);
    }
  }
  
  if (weights.length < 2) {
    return null; // Insufficient neighbors
  }
  
  // Calculate weighted interpolation
  const totalWeight = weights.reduce((sum, w) => sum + w, 0);
  const interpolatedValue = weights.reduce((sum, weight, i) => {
    return sum + (weight * values[i]);
  }, 0) / totalWeight;
  
  // Calculate uncertainty
  const interpolationUncertainty = 1 / Math.sqrt(totalWeight);
  const avgCalibrationUncertainty = uncertainties.reduce((sum, u) => sum + u, 0) / uncertainties.length;
  const totalUncertainty = Math.sqrt(
    interpolationUncertainty ** 2 + avgCalibrationUncertainty ** 2
  );
  
  return {
    value: Math.max(0, interpolatedValue),
    uncertainty: totalUncertainty,
    neighbors: weights.length,
    method: 'idw'
  };
}

/**
 * Get color for PM2.5 value based on WHO air quality guidelines
 */
export function getColorForValue(pm25Value) {
  if (pm25Value <= 12) return '#10b981';      // Good - Green
  if (pm25Value <= 35) return '#f59e0b';      // Moderate - Yellow
  if (pm25Value <= 55) return '#ef4444';      // Unhealthy for Sensitive - Orange
  if (pm25Value <= 150) return '#dc2626';     // Unhealthy - Red
  return '#991b1b';                           // Very Unhealthy - Dark Red
}

/**
 * Get opacity based on uncertainty (lower uncertainty = higher opacity)
 */
export function getOpacityForUncertainty(uncertainty) {
  const maxUncertainty = 30;
  const normalizedUncertainty = Math.min(uncertainty / maxUncertainty, 1);
  return Math.max(0.3, 1 - normalizedUncertainty * 0.6);
}
