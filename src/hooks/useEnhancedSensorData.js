import { useState, useEffect, useCallback, useRef } from 'react';
import { enhancedSensorAPI, weatherAPI } from '../services/enhancedApi';

// Enhanced configuration constants
const DEFAULT_FETCH_INTERVAL = 30000; // 30 seconds
const ERROR_RETRY_INTERVAL = 60000; // 1 minute
const MAX_RETRY_ATTEMPTS = 3;
const BBOX_GLOBAL = null; // Global coverage - no geographic restrictions
export const useEnhancedSensorData = (options = {}) => {
  const {
    bbox = BBOX_GLOBAL,
    enableAutoRefresh = true,
    fetchInterval = DEFAULT_FETCH_INTERVAL,
    enablePurpleAir = true,
    enableSensorCommunity = true,
    enableOpenAQ = true,
    enableWeather = true,
    enableSatellite = false
  } = options;

  // Enhanced state management
  const [sensorData, setSensorData] = useState([]);
  const [weatherData, setWeatherData] = useState([]);
  const [satelliteData, setSatelliteData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [enhancedStats, setEnhancedStats] = useState({
    total: 0,
    purpleair: 0,
    sensor_community: 0,
    openaq: 0,
    weather_points: 0,
    satellite_layers: 0,
    errors: []
  });

  // Refs for managing intervals and preventing memory leaks
  const intervalRef = useRef(null);
  const retryCountRef = useRef(0);
  const isComponentMountedRef = useRef(true);

  // Enhanced data aggregation with multiple sources
  const aggregateEnhancedData = useCallback((response) => {
    try {
      const sensors = response.sensors || [];
      const weather = response.weather || [];
      const satellite = response.satellite || {};
      const statistics = response.statistics || {};

      // Process sensor data with enhanced metadata
      const processedSensors = sensors.map(sensor => ({
        ...sensor,
        uniqueId: `${sensor.source}_${sensor.sensor_id}_${sensor.latitude}_${sensor.longitude}`,
        lastUpdated: new Date().toISOString(),
        dataQuality: calculateDataQuality(sensor),
          pollutionLevel: calculatePollutionLevel(sensor)
      }));

     // Enhanced statistics
      const enhancedStatistics = {
        total: processedSensors.length,
        purpleair: statistics.purpleair || 0,
        sensor_community: statistics.sensor_community || 0,
        openaq: statistics.openaq || 0,
        weather_points: weather.length,
        satellite_layers: Object.keys(satellite.layers || {}).length,
        errors: statistics.errors || [],
        coverage: calculateCoverage(processedSensors, bbox),
        averageValues: calculateAverageValues(processedSensors)
      };

      return {
        sensors: processedSensors,
        weather: weather,
        satellite: satellite,
        statistics: enhancedStatistics
      };
    } catch (error) {
      console.error('Error aggregating enhanced data:', error);
      return {
        sensors: [],
        weather: [],
        satellite: {},
        statistics: { total: 0, errors: [error.message] }
      };
    }
  }, [bbox]);

  // Calculate data quality score
  const calculateDataQuality = useCallback((sensor) => {
    let qualityScore = 0;
    let totalParams = 0;

    // Check for key parameters
    const params = ['pm25', 'pm10', 'temperature', 'humidity'];
    params.forEach(param => {
      if (sensor[param] !== null && sensor[param] !== undefined && !isNaN(sensor[param])) {
        qualityScore += 25;
      }
      totalParams += 25;
    });

    return (qualityScore / totalParams) * 100;
  }, []);

  // Calculate pollution level category
  const calculatePollutionLevel = useCallback((sensor) => {
    const pm25 = sensor.pm25;
    if (pm25 === null || pm25 === undefined) return 'unknown';
    
    if (pm25 <= 12) return 'good';
    if (pm25 <= 35) return 'moderate';
    if (pm25 <= 55) return 'unhealthy_sensitive';
    if (pm25 <= 150) return 'unhealthy';
    return 'very_unhealthy';
  }, []);

  // Calculate geographic coverage
  const calculateCoverage = useCallback((sensors, bbox) => {
    if (!sensors.length || !bbox) return 0;

    const [west, south, east, north] = bbox;
    const area = (east - west) * (north - south);
    const sensorDensity = sensors.length / area;
    
    return Math.min(100, sensorDensity * 10); // Normalize to 0-100
  }, []);

  // Calculate average values across all sensors
  const calculateAverageValues = useCallback((sensors) => {
    const values = { pm25: [], pm10: [], temperature: [], humidity: [] };
    
    sensors.forEach(sensor => {
      if (sensor.pm25 !== null && !isNaN(sensor.pm25)) values.pm25.push(sensor.pm25);
      if (sensor.pm10 !== null && !isNaN(sensor.pm10)) values.pm10.push(sensor.pm10);
      if (sensor.temperature !== null && !isNaN(sensor.temperature)) values.temperature.push(sensor.temperature);
      if (sensor.humidity !== null && !isNaN(sensor.humidity)) values.humidity.push(sensor.humidity);
    });

    const averages = {};
    Object.keys(values).forEach(key => {
      if (values[key].length > 0) {
        averages[key] = values[key].reduce((sum, val) => sum + val, 0) / values[key].length;
      }
    });

    return averages;
  }, []);

  // Enhanced data fetch with multiple sources
  const fetchEnhancedSensorData = useCallback(async (isRetry = false) => {
    if (!isComponentMountedRef.current) return;

    try {
      if (!isRetry) {
        setLoading(true);
        setError(null);
      }

      const bboxString = Array.isArray(bbox) ? bbox.join(',') : bbox;

      // Fetch enhanced integration data
      const response = await enhancedSensorAPI.getEnhancedIntegration(
        bboxString,
        enableSatellite,
        enableWeather,
        new Date().toISOString().split('T')[0]
      );

      if (response.success) {
        const aggregatedData = aggregateEnhancedData(response);
        
        if (isComponentMountedRef.current) {
          setSensorData(aggregatedData.sensors);
          setWeatherData(aggregatedData.weather);
          setSatelliteData(aggregatedData.satellite);
          setEnhancedStats(aggregatedData.statistics);
          setLastUpdated(new Date());
          
          // Only show error if we have no data at all
          if (aggregatedData.sensors.length === 0) {
            setError({
              type: 'warning',
              message: 'Using demo data - external APIs unavailable',
              timestamp: new Date()
            });
          } else {
            setError(null);
          }
          
          retryCountRef.current = 0;
        }
      } else {
        // Don't throw error, the API call already provides fallback data
        console.log('API returned fallback data');
      }

    } catch (err) {
      console.error('Enhanced sensor data fetch error:', err);
      
      if (isComponentMountedRef.current) {
        // Only set error if we have absolutely no data
        if (sensorData.length === 0) {
          setError({
            type: 'info',
            message: 'Loading demo sensor data for demonstration',
            timestamp: new Date()
          });
        }
        // Implement exponential backoff for retries
        retryCountRef.current += 1;
         if (retryCountRef.current <= MAX_RETRY_ATTEMPTS && sensorData.length === 0) {
          const retryDelay = Math.min(ERROR_RETRY_INTERVAL * Math.pow(2, retryCountRef.current - 1), 300000);
          console.log(`Retrying enhanced fetch in ${retryDelay}ms (attempt ${retryCountRef.current}/${MAX_RETRY_ATTEMPTS})`);
          
          setTimeout(() => {
            if (isComponentMountedRef.current) {
              fetchEnhancedSensorData(true);
            }
          }, retryDelay);
        }
      }
    } finally {
      if (isComponentMountedRef.current && !isRetry) {
        setLoading(false);
      }
    }
  }, [bbox, enableSatellite, enableWeather, aggregateEnhancedData]);

  // Manual refresh function
  const refreshEnhancedData = useCallback(() => {
    retryCountRef.current = 0;
    fetchEnhancedSensorData(false);
  }, [fetchEnhancedSensorData]);

  // Get sensors by source with enhanced filtering
  const getSensorsBySource = useCallback((source) => {
    return sensorData.filter(sensor => sensor.source === source);
  }, [sensorData]);

  // Get sensors by pollution level
  const getSensorsByPollutionLevel = useCallback((level) => {
    return sensorData.filter(sensor => sensor.pollutionLevel === level);
  }, [sensorData]);

  // Get high quality sensors
  const getHighQualitySensors = useCallback((minQuality = 75) => {
    return sensorData.filter(sensor => sensor.dataQuality >= minQuality);
  }, [sensorData]);

  // Set up automatic refresh interval
  useEffect(() => {
    if (!enableAutoRefresh) return;

    // Clear existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    // Set up new interval
    intervalRef.current = setInterval(() => {
      if (isComponentMountedRef.current && !loading) {
        fetchEnhancedSensorData(false);
      }
    }, fetchInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enableAutoRefresh, fetchInterval, fetchEnhancedSensorData, loading]);

  // Initial data fetch
  useEffect(() => {
    isComponentMountedRef.current = true;
    fetchEnhancedSensorData(false);

    return () => {
      isComponentMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchEnhancedSensorData]);

  return {
    // Enhanced data
    sensorData,
    weatherData,
    satelliteData,
    enhancedStats,
    lastUpdated,
    
    // State
    loading,
    error,
    
    // Actions
    refreshEnhancedData,
    getSensorsBySource,
    getSensorsByPollutionLevel,
    getHighQualitySensors,
    
    // Meta information
    isConnected: !error || error.type === 'warning',
    retryCount: retryCountRef.current,
    dataSourcesActive: {
      purpleair: enablePurpleAir,
      sensor_community: enableSensorCommunity,
      openaq: enableOpenAQ,
      weather: enableWeather,
      satellite: enableSatellite
    }
  };
};

export default useEnhancedSensorData;