import React from 'react';

class CanvasMarkerService {
  constructor() {
    this.markerCache = new Map();
    this.canvasPool = [];
    this.maxPoolSize = 100;
    
    // Marker configurations
    this.markerStyles = {
      default: {
        radius: 8,
        strokeWidth: 2,
        strokeColor: '#ffffff',
        shadowBlur: 4,
        shadowColor: 'rgba(0,0,0,0.3)'
      },
      selected: {
        radius: 12,
        strokeWidth: 3,
        strokeColor: '#3b82f6',
        shadowBlur: 6,
        shadowColor: 'rgba(59,130,246,0.4)'
      },
      clustered: {
        radius: 16,
        strokeWidth: 2,
        strokeColor: '#ffffff',
        fontSize: 12,
        fontWeight: 'bold',
        fontColor: '#ffffff'
      }
    };
    
    // Color mappings for different pollution levels
    this.pollutionColors = {
      good: '#10b981',         // Green
      moderate: '#f59e0b',     // Yellow
      unhealthy_sensitive: '#ef4444',  // Orange
      unhealthy: '#dc2626',    // Red
      very_unhealthy: '#991b1b', // Dark red
      hazardous: '#7c2d12'     // Brown
    };
  }
  
  /**
   * Create stable canvas-based marker
   */
  createCanvasMarker(sensor, style = 'default', isSelected = false) {
    const cacheKey = this._generateCacheKey(sensor, style, isSelected);
    
    // Check cache first
    if (this.markerCache.has(cacheKey)) {
      return this.markerCache.get(cacheKey);
    }
    
    // Create new canvas marker
    const canvas = this._getCanvas();
    const ctx = canvas.getContext('2d');
    const markerStyle = this.markerStyles[isSelected ? 'selected' : style];
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Set canvas size based on marker size
    const size = markerStyle.radius * 3; // Padding for shadow
    canvas.width = size;
    canvas.height = size;
    
    // Calculate center
    const centerX = size / 2;
    const centerY = size / 2;
    
    // Draw shadow
    this._drawShadow(ctx, centerX, centerY + 2, markerStyle);
    
    // Draw marker based on type
    if (style === 'clustered') {
      this._drawClusterMarker(ctx, centerX, centerY, sensor, markerStyle);
    } else {
      this._drawSensorMarker(ctx, centerX, centerY, sensor, markerStyle);
    }
    
    // Create data URL
    const dataUrl = canvas.toDataURL('image/png');
    
    // Cache the result
    this.markerCache.set(cacheKey, dataUrl);
    
    // Return canvas to pool
    this._returnCanvas(canvas);
    
    return dataUrl;
  }
  
  /**
   * Create marker icon for Leaflet
   */
  createLeafletIcon(sensor, style = 'default', isSelected = false) {
    const dataUrl = this.createCanvasMarker(sensor, style, isSelected);
    const markerStyle = this.markerStyles[isSelected ? 'selected' : style];
    const size = markerStyle.radius * 2;
    
    return L.icon({
      iconUrl: dataUrl,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
      popupAnchor: [0, -size / 2],
      className: 'canvas-marker-icon'
    });
  }
  
  /**
   * Create marker element for Mapbox
   */
  createMapboxElement(sensor, style = 'default', isSelected = false) {
    const dataUrl = this.createCanvasMarker(sensor, style, isSelected);
    const markerStyle = this.markerStyles[isSelected ? 'selected' : style];
    const size = markerStyle.radius * 2;
    
    const element = document.createElement('div');
    element.className = 'canvas-marker-element';
    element.style.cssText = `
      width: ${size}px;
      height: ${size}px;
      background-image: url(${dataUrl});
      background-size: contain;
      background-repeat: no-repeat;
      background-position: center;
      cursor: pointer;
      transform-origin: center center;
    `;
    
    return element;
  }
  
  /**
   * Draw sensor marker on canvas
   */
  _drawSensorMarker(ctx, centerX, centerY, sensor, style) {
    const pollutionLevel = this._getPollutionLevel(sensor.pm25 || 0);
    const fillColor = this.pollutionColors[pollutionLevel];
    
    // Draw main circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, style.radius, 0, 2 * Math.PI);
    ctx.fillStyle = fillColor;
    ctx.fill();
    
    // Draw stroke
    ctx.lineWidth = style.strokeWidth;
    ctx.strokeStyle = style.strokeColor;
    ctx.stroke();
    
    // Draw source indicator
    const sourceIndicator = this._getSourceIndicator(sensor.source);
    if (sourceIndicator) {
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${style.radius * 0.6}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(sourceIndicator, centerX, centerY);
    }
  }
  
  /**
   * Draw cluster marker on canvas
   */
  _drawClusterMarker(ctx, centerX, centerY, cluster, style) {
    const count = cluster.count || cluster.sensors?.length || 1;
    const maxPollution = cluster.maxPollution || 0;
    const pollutionLevel = this._getPollutionLevel(maxPollution);
    const fillColor = this.pollutionColors[pollutionLevel];
    
    // Draw cluster circle with size based on count
    const radius = Math.min(style.radius + Math.log10(count) * 4, 30);
    
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.fillStyle = fillColor;
    ctx.fill();
    
    // Draw stroke
    ctx.lineWidth = style.strokeWidth;
    ctx.strokeStyle = style.strokeColor;
    ctx.stroke();
    
    // Draw count text
    ctx.fillStyle = style.fontColor;
    ctx.font = `${style.fontWeight} ${style.fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(count.toString(), centerX, centerY);
  }
  
  /**
   * Draw shadow effect
   */
  _drawShadow(ctx, x, y, style) {
    ctx.shadowBlur = style.shadowBlur;
    ctx.shadowColor = style.shadowColor;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 2;
    
    // Draw invisible circle to create shadow
    ctx.beginPath();
    ctx.arc(x, y - 2, style.radius, 0, 2 * Math.PI);
    ctx.fillStyle = 'rgba(0,0,0,0.1)';
    ctx.fill();
    
    // Reset shadow
    ctx.shadowBlur = 0;
    ctx.shadowColor = 'transparent';
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
  }
  
  /**
   * Get pollution level category
   */
  _getPollutionLevel(pm25Value) {
    if (pm25Value <= 12) return 'good';
    if (pm25Value <= 35) return 'moderate';
    if (pm25Value <= 55) return 'unhealthy_sensitive';
    if (pm25Value <= 150) return 'unhealthy';
    if (pm25Value <= 250) return 'very_unhealthy';
    return 'hazardous';
  }
  
  /**
   * Get source indicator character
   */
  _getSourceIndicator(source) {
    const indicators = {
      purpleair: 'P',
      sensor_community: 'S',
      openaq: 'O',
      uploaded: 'U'
    };
    return indicators[source] || '•';
  }
  
  /**
   * Generate cache key for marker
   */
  _generateCacheKey(sensor, style, isSelected) {
    const pm25 = sensor.pm25 || 0;
    const source = sensor.source || 'unknown';
    return `${style}_${source}_${this._getPollutionLevel(pm25)}_${isSelected}`;
  }
  
  /**
   * Get canvas from pool or create new one
   */
  _getCanvas() {
    return this.canvasPool.pop() || document.createElement('canvas');
  }
  
  /**
   * Return canvas to pool for reuse
   */
  _returnCanvas(canvas) {
    if (this.canvasPool.length < this.maxPoolSize) {
      // Clear canvas before returning to pool
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      this.canvasPool.push(canvas);
    }
  }
  
  /**
   * Clear marker cache to free memory
   */
  clearCache() {
    this.markerCache.clear();
    logger.info('Canvas marker cache cleared');
  }
  
  /**
   * Get cache statistics
   */
  getCacheStats() {
    return {
      cached_markers: this.markerCache.size,
      canvas_pool_size: this.canvasPool.length,
      memory_usage_estimate: this.markerCache.size * 2048 // Rough estimate in bytes
    };
  }
}

// Singleton instance
const canvasMarkerService = new CanvasMarkerService();

export default canvasMarkerService;
