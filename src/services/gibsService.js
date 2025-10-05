import axios from 'axios';

class GIBSService {
  constructor() {
    // NASA GIBS WMTS tiles are PUBLIC - no API key needed!
    this.baseUrl = 'https://gibs.earthdata.nasa.gov/wmts/epsg4326/best';
    this.capabilitiesUrl = 'https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities';
  }

  // Generate proper GIBS tile URL
  generateTileUrl(layerId, date, z, x, y, format = 'jpg') {
    try {
      const dateStr = this.formatDate(date);
      const tileMatrix = this.getTileMatrix(z);
      
      // GIBS WMTS URL pattern: {base}/{layer}/default/{date}/{tileMatrixSet}/{z}/{y}/{x}.{format}
      return `${this.baseUrl}/${layerId}/default/${dateStr}/${tileMatrix}/${z}/${y}/${x}.${format}`;
    } catch (error) {
      console.error('Error generating GIBS tile URL:', error);
      return null;
    }
  }

  // Format date for GIBS (YYYY-MM-DD)
  formatDate(date) {
    if (typeof date === 'string') {
      return date.split('T')[0]; // Remove time component
    }
    if (date instanceof Date) {
      return date.toISOString().split('T')[0];
    }
    return new Date().toISOString().split('T')[0];
  }

  // Get appropriate tile matrix set based on zoom level
  getTileMatrix(zoom) {
    if (zoom <= 2) return '2km';
    if (zoom <= 5) return '1km';
    if (zoom <= 7) return '500m';
    return '250m';
  }

  // Get available GIBS layers
  getAvailableLayers() {
    return [
      {
        id: 'MODIS_Terra_CorrectedReflectance_TrueColor',
        name: 'MODIS Terra True Color',
        description: 'True color corrected reflectance from MODIS Terra',
        format: 'jpg',
        temporal: true,
        category: 'imagery'
      },
      {
        id: 'MODIS_Aqua_CorrectedReflectance_TrueColor',
        name: 'MODIS Aqua True Color',
        description: 'True color corrected reflectance from MODIS Aqua',
        format: 'jpg',
        temporal: true,
        category: 'imagery'
      },
      {
        id: 'MODIS_Terra_Land_Surface_Temp_Day',
        name: 'Land Surface Temperature (Day)',
        description: 'Daytime land surface temperature from MODIS Terra',
        format: 'png',
        temporal: true,
        category: 'temperature'
      },
      {
        id: 'MODIS_Terra_Aerosol',
        name: 'Aerosol Optical Depth',
        description: 'Aerosol optical depth from MODIS Terra',
        format: 'png',
        temporal: true,
        category: 'atmospheric'
      },
      {
        id: 'AIRS_L2_Surface_Air_Temperature_Day',
        name: 'AIRS Surface Air Temperature',
        description: 'Surface air temperature from AIRS',
        format: 'png',
        temporal: true,
        category: 'temperature'
      }
    ];
  }

  // Test if GIBS layer is accessible
  async testLayerAccess(layerId, date = null) {
    try {
      const testDate = date || new Date().toISOString().split('T')[0];
      const testUrl = this.generateTileUrl(layerId, testDate, 0, 0, 0);
      
      const response = await axios.head(testUrl, { timeout: 5000 });
      return {
        accessible: response.status === 200,
        url: testUrl,
        status: response.status
      };
    } catch (error) {
      return {
        accessible: false,
        url: null,
        error: error.message
      };
    }
  }

  // Validate layer configuration
  validateLayer(layerId, date) {
    const layers = this.getAvailableLayers();
    const layer = layers.find(l => l.id === layerId);
    
    if (!layer) {
      return { valid: false, error: 'Layer not found' };
    }

    if (layer.temporal && date) {
      const layerDate = new Date(date);
      const today = new Date();
      
      // Check if date is too far in the future
      if (layerDate > today) {
        return { valid: false, error: 'Date is in the future' };
      }
    }

    return { valid: true, layer };
  }
}

export default new GIBSService();
