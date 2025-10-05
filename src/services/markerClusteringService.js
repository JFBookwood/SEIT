import Supercluster from 'supercluster';

class MarkerClusteringService {
  constructor() {
    // Clustering configurations for different zoom levels
    this.clusterConfigs = {
      default: {
        radius: 80,        // Cluster radius in pixels
        maxZoom: 15,       // Max zoom to cluster markers
        minZoom: 2,        // Min zoom for clustering
        minPoints: 2,      // Minimum points to form cluster
        extent: 512,       // Tile extent
        nodeSize: 64       // Size of KD-tree node
      },
      dense: {
        radius: 120,       // Larger radius for dense areas
        maxZoom: 17,
        minZoom: 2,
        minPoints: 3,
        extent: 512,
        nodeSize: 32
      },
      sparse: {
        radius: 40,        // Smaller radius for sparse areas
        maxZoom: 12,
        minZoom: 2,
        minPoints: 2,
        extent: 512,
        nodeSize: 128
      }
    };
    
    // Active cluster instances
    this.clusters = new Map();
    
    // Density thresholds
    this.densityThresholds = {
      sparse: 0.1,    // sensors per km²
      medium: 1.0,
      dense: 5.0
    };
  }
  
  /**
   * Initialize clustering for sensor data
   */
  initializeClustering(sensorData, mapBounds, configType = 'default') {
    try {
      const clusterKey = `${configType}_${this._generateBoundsKey(mapBounds)}`;
      
      // Convert sensor data to GeoJSON format for clustering
      const geoJsonFeatures = this._convertToGeoJSON(sensorData);
      
      if (geoJsonFeatures.length === 0) {
        console.warn('No valid sensor data for clustering');
        return { clusters: [], points: [] };
      }
      
      // Calculate data density to choose optimal config
      const density = this._calculateDataDensity(sensorData, mapBounds);
      const optimalConfig = this._selectConfigByDensity(density);
      
      // Create Supercluster instance
      const supercluster = new Supercluster({
        ...this.clusterConfigs[optimalConfig],
        map: (props) => ({
          // Aggregate pollution data for clusters
          pm25_sum: props.pm25 || 0,
          pm25_max: props.pm25 || 0,
          sensor_count: 1,
          source_breakdown: { [props.source]: 1 }
        }),
        reduce: (accumulated, props) => {
          accumulated.pm25_sum += props.pm25_sum;
          accumulated.pm25_max = Math.max(accumulated.pm25_max, props.pm25_max);
          accumulated.sensor_count += props.sensor_count;
          
          // Merge source breakdown
          for (const [source, count] of Object.entries(props.source_breakdown)) {
            accumulated.source_breakdown[source] = (accumulated.source_breakdown[source] || 0) + count;
          }
        }
      });
      
      // Load sensor data into clusterer
      supercluster.load(geoJsonFeatures);
      
      // Cache the cluster instance
      this.clusters.set(clusterKey, {
        supercluster,
        config: optimalConfig,
        density,
        lastUpdated: Date.now()
      });
      
      console.log(`Clustering initialized: ${geoJsonFeatures.length} sensors, density: ${density.toFixed(2)}/km², config: ${optimalConfig}`);
      
      return { supercluster, config: optimalConfig };
      
    } catch (error) {
      console.error('Clustering initialization failed:', error);
      return { clusters: [], points: sensorData };
    }
  }
  
  /**
   * Get clusters and points for current map view
   */
  getClustersForBounds(mapBounds, zoom, clusterKey = null) {
    try {
      // Find appropriate cluster instance
      let clusterInstance = null;
      
      if (clusterKey && this.clusters.has(clusterKey)) {
        clusterInstance = this.clusters.get(clusterKey);
      } else {
        // Find most recent cluster instance
        const clusterEntries = Array.from(this.clusters.values());
        if (clusterEntries.length > 0) {
          clusterInstance = clusterEntries.reduce((latest, current) => 
            current.lastUpdated > latest.lastUpdated ? current : latest
          );
        }
      }
      
      if (!clusterInstance) {
        console.warn('No cluster instance available');
        return { clusters: [], points: [] };
      }
      
      const { supercluster } = clusterInstance;
      
      // Convert bounds to Supercluster format [west, south, east, north]
      const bbox = [
        mapBounds.west || mapBounds[0],
        mapBounds.south || mapBounds[1], 
        mapBounds.east || mapBounds[2],
        mapBounds.north || mapBounds[3]
      ];
      
      // Validate bounds
      if (!this._validateBounds(bbox)) {
        console.warn('Invalid map bounds for clustering:', bbox);
        return { clusters: [], points: [] };
      }
      
      // Get clusters for current view
      const clustersAndPoints = supercluster.getClusters(bbox, Math.floor(zoom));
      
      // Separate clusters from individual points
      const clusters = [];
      const points = [];
      
      for (const item of clustersAndPoints) {
        if (item.properties.cluster) {
          // This is a cluster
          const clusterInfo = {
            id: item.properties.cluster_id,
            coordinates: item.geometry.coordinates,
            count: item.properties.point_count,
            sensors: item.properties.sensor_count,
            maxPollution: item.properties.pm25_max,
            avgPollution: item.properties.pm25_sum / item.properties.sensor_count,
            sourceBreakdown: item.properties.source_breakdown,
            bounds: this._getClusterBounds(supercluster, item.properties.cluster_id)
          };
          clusters.push(clusterInfo);
        } else {
          // This is an individual sensor
          points.push({
            id: item.properties.sensor_id,
            coordinates: item.geometry.coordinates,
            sensor: item.properties
          });
        }
      }
      
      return { clusters, points };
      
    } catch (error) {
      console.error('Error getting clusters for bounds:', error);
      return { clusters: [], points: [] };
    }
  }
  
  /**
   * Get children of a cluster for expansion
   */
  getClusterChildren(clusterId, clusterKey = null) {
    try {
      const clusterInstance = this._getClusterInstance(clusterKey);
      if (!clusterInstance) return [];
      
      const children = clusterInstance.supercluster.getChildren(clusterId);
      
      return children.map(child => ({
        id: child.properties.cluster ? child.properties.cluster_id : child.properties.sensor_id,
        isCluster: !!child.properties.cluster,
        coordinates: child.geometry.coordinates,
        properties: child.properties
      }));
      
    } catch (error) {
      console.error('Error getting cluster children:', error);
      return [];
    }
  }
  
  /**
   * Get cluster expansion zoom level
   */
  getClusterExpansionZoom(clusterId, clusterKey = null) {
    try {
      const clusterInstance = this._getClusterInstance(clusterKey);
      if (!clusterInstance) return null;
      
      return clusterInstance.supercluster.getClusterExpansionZoom(clusterId);
      
    } catch (error) {
      console.error('Error getting expansion zoom:', error);
      return null;
    }
  }
  
  /**
   * Convert sensor data to GeoJSON format
   */
  _convertToGeoJSON(sensorData) {
    const features = [];
    
    for (const sensor of sensorData) {
      // Validate coordinates
      const lat = parseFloat(sensor.latitude);
      const lon = parseFloat(sensor.longitude);
      
      if (isNaN(lat) || isNaN(lon) || 
          lat < -90 || lat > 90 || 
          lon < -180 || lon > 180) {
        console.warn(`Invalid coordinates for sensor ${sensor.sensor_id}: ${lat}, ${lon}`);
        continue;
      }
      
      const feature = {
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [lon, lat]
        },
        properties: {
          sensor_id: sensor.sensor_id || sensor.id,
          pm25: parseFloat(sensor.pm25) || 0,
          pm10: parseFloat(sensor.pm10) || 0,
          temperature: parseFloat(sensor.temperature) || null,
          humidity: parseFloat(sensor.humidity) || null,
          source: sensor.source || 'unknown',
          timestamp: sensor.timestamp,
          metadata: sensor.metadata || {}
        }
      };
      
      features.push(feature);
    }
    
    console.log(`Converted ${features.length} sensors to GeoJSON features`);
    return features;
  }
  
  /**
   * Calculate data density for config selection
   */
  _calculateDataDensity(sensorData, bounds) {
    if (!bounds || sensorData.length === 0) return 0;
    
    const area = this._calculateBoundsArea(bounds);
    return sensorData.length / area;
  }
  
  /**
   * Calculate area of bounding box in km²
   */
  _calculateBoundsArea(bounds) {
    const [west, south, east, north] = Array.isArray(bounds) 
      ? bounds 
      : [bounds.west, bounds.south, bounds.east, bounds.north];
    
    // Rough area calculation (not accounting for Earth curvature)
    const latDiff = north - south;
    const lonDiff = east - west;
    
    // Convert degrees to approximate km (111km per degree)
    const areaKm2 = Math.abs(latDiff * lonDiff) * 111 * 111;
    
    return Math.max(areaKm2, 1); // Minimum 1 km² to avoid division by zero
  }
  
  /**
   * Select optimal config based on data density
   */
  _selectConfigByDensity(density) {
    if (density > this.densityThresholds.dense) {
      return 'dense';
    } else if (density > this.densityThresholds.medium) {
      return 'default';
    } else {
      return 'sparse';
    }
  }
  
  /**
   * Get cluster bounds
   */
  _getClusterBounds(supercluster, clusterId) {
    try {
      const children = supercluster.getChildren(clusterId);
      
      let minLat = Infinity, maxLat = -Infinity;
      let minLon = Infinity, maxLon = -Infinity;
      
      for (const child of children) {
        const [lon, lat] = child.geometry.coordinates;
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);
      }
      
      return [minLon, minLat, maxLon, maxLat];
      
    } catch (error) {
      return null;
    }
  }
  
  /**
   * Validate bounding box
   */
  _validateBounds(bbox) {
    const [west, south, east, north] = bbox;
    
    return (
      typeof west === 'number' && typeof south === 'number' &&
      typeof east === 'number' && typeof north === 'number' &&
      west >= -180 && west <= 180 &&
      east >= -180 && east <= 180 &&
      south >= -90 && south <= 90 &&
      north >= -90 && north <= 90 &&
      west < east && south < north
    );
  }
  
  /**
   * Generate bounds key for caching
   */
  _generateBoundsKey(bounds) {
    if (Array.isArray(bounds)) {
      return bounds.map(b => b.toFixed(2)).join('_');
    }
    return `${bounds.west}_${bounds.south}_${bounds.east}_${bounds.north}`;
  }
  
  /**
   * Get cluster instance by key
   */
  _getClusterInstance(clusterKey) {
    if (clusterKey && this.clusters.has(clusterKey)) {
      return this.clusters.get(clusterKey);
    }
    
    // Return most recent if no specific key
    const entries = Array.from(this.clusters.values());
    return entries.length > 0 ? entries[entries.length - 1] : null;
  }
  
  /**
   * Clean up old cluster instances
   */
  cleanup(maxAge = 300000) { // 5 minutes
    const now = Date.now();
    const keysToDelete = [];
    
    for (const [key, instance] of this.clusters.entries()) {
      if (now - instance.lastUpdated > maxAge) {
        keysToDelete.push(key);
      }
    }
    
    for (const key of keysToDelete) {
      this.clusters.delete(key);
    }
    
    if (keysToDelete.length > 0) {
      console.log(`Cleaned up ${keysToDelete.length} old cluster instances`);
    }
  }
  
  /**
   * Get clustering statistics
   */
  getClusteringStats() {
    return {
      active_clusters: this.clusters.size,
      configs_available: Object.keys(this.clusterConfigs),
      density_thresholds: this.densityThresholds,
      cache_stats: Array.from(this.clusters.entries()).map(([key, instance]) => ({
        key,
        config: instance.config,
        density: instance.density,
        age_seconds: (Date.now() - instance.lastUpdated) / 1000
      }))
    };
  }
}

// Singleton instance
const markerClusteringService = new MarkerClusteringService();

export default markerClusteringService;
