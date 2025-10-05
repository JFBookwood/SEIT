/**
 * Calculate distance between two coordinates using Haversine formula
 * Returns distance in meters
 */
export function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Earth's radius in meters
  
  const lat1Rad = toRadians(lat1);
  const lat2Rad = toRadians(lat2);
  const deltaLat = toRadians(lat2 - lat1);
  const deltaLon = toRadians(lon2 - lon1);
  
  const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(lat1Rad) * Math.cos(lat2Rad) *
    Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  
  return R * c;
}

/**
 * Convert degrees to radians
 */
function toRadians(degrees) {
  return degrees * (Math.PI / 180);
}

/**
 * Calculate bounds area in square kilometers
 */
export function calculateBoundsArea(bounds) {
  const [west, south, east, north] = bounds;
  
  const width = calculateDistance(south, west, south, east);
  const height = calculateDistance(south, west, north, west);
  
  return (width * height) / 1000000; // Convert to km²
}

/**
 * Check if point is within bounds
 */
export function isPointInBounds(lat, lon, bounds) {
  const [west, south, east, north] = bounds;
  return lat >= south && lat <= north && lon >= west && lon <= east;
}
