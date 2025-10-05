import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging and error handling
apiClient.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    
    // Handle specific error cases
    if (error.code === 'ECONNABORTED') {
      error.message = 'Request timeout - server is taking too long to respond';
    } else if (error.response?.status === 500) {
      error.message = 'Server error - please try again later';
    } else if (error.response?.status === 404) {
      error.message = 'API endpoint not found';
    } else if (!error.response) {
      error.message = 'Network error - please check your connection';
    }
    
    return Promise.reject(error);
  }
);

// API service functions
export const sensorAPI = {
  // Get PurpleAir sensors
  async getPurpleAirSensors(bbox = null, limit = 100) {
    try {
      const params = { limit };
      if (bbox) {
        params.bbox = bbox;
      }
      
      const response = await apiClient.get('/sensors/purpleair/sensors', { params });
      return {
        success: true,
        data: response.data.sensors || [],
        total: response.data.total || 0,
        source: 'purpleair'
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: [],
        source: 'purpleair'
      };
    }
  },

  // Get Sensor.Community sensors
  async getSensorCommunityData(bbox = null) {
    try {
      const params = {};
      if (bbox) {
        params.bbox = bbox;
      }
      
      const response = await apiClient.get('/sensors/sensor-community/sensors', { params });
      return {
        success: true,
        data: response.data.sensors || [],
        total: response.data.total || 0,
        source: 'sensor_community'
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: [],
        source: 'sensor_community'
      };
    }
  },

  // Get stored sensor data with filters
  async getStoredSensorData(filters = {}) {
    try {
      const response = await apiClient.get('/sensors/data', { params: filters });
      return {
        success: true,
        data: response.data.data || [],
        total: response.data.total || 0,
        filters: response.data.filters_applied || {},
        source: 'stored'
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: [],
        source: 'stored'
      };
    }
  },

  // Get sensor history for detail panel
  async getSensorHistory(sensorId, startTimestamp, endTimestamp, average = 60) {
    try {
      const response = await apiClient.get(`/sensors/purpleair/sensor/${sensorId}/history`, {
        params: {
          start_timestamp: startTimestamp,
          end_timestamp: endTimestamp,
          average
        }
      });
      return {
        success: true,
        data: response.data.data || [],
        sensorId
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: [],
        sensorId
      };
    }
  },

  // Sync PurpleAir data to database
  async syncPurpleAirData(bbox, hoursBack = 24) {
    try {
      const response = await apiClient.post('/sensors/sync/purpleair', {
        bbox,
        hours_back: hoursBack
      });
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }
};

export const analyticsAPI = {
  // Get analytics summary
  async getSummary(bbox, startDate, endDate) {
    try {
      const response = await apiClient.get('/analytics/summary', {
        params: {
          bbox: bbox.join(','),
          start_date: startDate,
          end_date: endDate
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

  // Run hotspot analysis
  async detectHotspots(bbox, startDate, endDate, options = {}) {
    try {
      const response = await apiClient.post('/analytics/hotspots', {
        bbox,
        start_date: startDate,
        end_date: endDate,
        ...options
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
  }
};

export const systemAPI = {
  // Health check
  async healthCheck() {
    try {
      const response = await apiClient.get('/health');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  },

  // Get system status
  async getSystemStatus() {
    try {
      const response = await apiClient.get('/admin/status');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }
};

export default apiClient;
