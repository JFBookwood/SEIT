import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// Create heatmap API client
const heatmapApiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 second timeout for grid generation
  headers: {
    'Content-Type': 'application/json',
  },
});

// Enhanced response interceptor
heatmapApiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('Heatmap API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const heatmapAPI = {
  // Get heatmap grid data
  async getHeatmapGrid(params) {
    try {
      const response = await heatmapApiClient.get('/heatmap/grid', { params });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Get vector tile
  async getVectorTile(z, x, y, params = {}) {
    try {
      const response = await heatmapApiClient.get(`/heatmap/tiles/${z}/${x}/${y}`, {
        params,
        responseType: 'arraybuffer'
      });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Get heatmap metadata
  async getHeatmapMetadata(bbox) {
    try {
      const bboxString = Array.isArray(bbox) ? bbox.join(',') : bbox;
      const response = await heatmapApiClient.get('/heatmap/metadata', {
        params: { bbox: bboxString }
      });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Get time series for specific location
  async getTimeSeriesData(location, bbox, params = {}) {
    try {
      const response = await heatmapApiClient.get('/heatmap/time-series', {
        params: {
          west: bbox[0],
          south: bbox[1],
          east: bbox[2],
          north: bbox[3],
          lat: location.latitude,
          lon: location.longitude,
          ...params
        }
      });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Precompute heatmap snapshots
  async precomputeSnapshots(bbox, params = {}) {
    try {
      const bboxString = Array.isArray(bbox) ? bbox.join(',') : bbox;
      const response = await heatmapApiClient.post('/heatmap/precompute', null, {
        params: {
          bbox: bboxString,
          ...params
        }
      });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Clear heatmap cache
  async clearCache(params = {}) {
    try {
      const response = await heatmapApiClient.delete('/heatmap/cache', { params });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  },

  // Get heatmap status
  async getStatus() {
    try {
      const response = await heatmapApiClient.get('/heatmap/status');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: null
      };
    }
  }
};

export default heatmapAPI;
