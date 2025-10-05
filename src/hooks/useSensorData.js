import { useState, useEffect, useCallback, useRef } from 'react';
import { sensorAPI } from '../services/api';

// Configuration constants
const DEFAULT_FETCH_INTERVAL = 30000; // 30 seconds
const ERROR_RETRY_INTERVAL = 60000; // 1 minute
const MAX_RETRY_ATTEMPTS = 3;
const BBOX_GLOBAL = null; // Global coverage - no geographic restrictions
export const useSensorData = (options = {}) => {
  const {
    bbox = BBOX_GLOBAL,
    enableAutoRefresh = true,
    fetchInterval = DEFAULT_FETCH_INTERVAL,
    enablePurpleAir = true,
    enableSensorCommunity = true,
    enableStoredData = false
  } = options;

  // State management
  const [sensorData, setSensorData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [dataStats, setDataStats] = useState({
    total: 0,
    purpleair: 0,
    sensor_community: 0,
    stored: 0
  });

  // Refs for managing intervals and preventing memory leaks
  const intervalRef = useRef(null);
  const retryCountRef = useRef(0);
  const isComponentMountedRef = useRef(true);

  // Data aggregation and deduplication
  const aggregateAndDeduplicateData = useCallback((dataArrays) => {
    const allData = [];
    const seenSensors = new Set();
    const stats = { total: 0, purpleair: 0, sensor_community: 0, stored: 0 };

    dataArrays.forEach(({ data, source }) => {
      data.forEach(sensor => {
        // Create unique identifier based on location and source
        const uniqueId = `${sensor.source || source}_${sensor.sensor_id}_${sensor.latitude}_${sensor.longitude}`;
        
        if (!seenSensors.has(uniqueId)) {
          seenSensors.add(uniqueId);
          
          // Normalize sensor data format
          const normalizedSensor = {
            ...sensor,
            source: sensor.source || source,
            uniqueId,
            lastUpdated: new Date().toISOString()
          };
          
          allData.push(normalizedSensor);
          stats[source] += 1;
          stats.total += 1;
        }
      });
    });

    return { sensors: allData, stats };
  }, []);

  // Fetch data from all enabled sources
  const fetchSensorData = useCallback(async (isRetry = false) => {
    if (!isComponentMountedRef.current) return;

    try {
      if (!isRetry) {
        setLoading(true);
        setError(null);
      }

      const fetchPromises = [];
      const bboxString = Array.isArray(bbox) ? bbox.join(',') : bbox;
      // Fetch from enabled sources
      if (enablePurpleAir) {
        fetchPromises.push(sensorAPI.getPurpleAirSensors(bboxString));
      }
      
      if (enableSensorCommunity) {
        fetchPromises.push(sensorAPI.getSensorCommunityData(bboxString));
      }
      
      if (enableStoredData) {
        fetchPromises.push(sensorAPI.getStoredSensorData({ 
          bbox: bboxString,
          limit: 1000 
        }));
      }

      // Execute all API calls concurrently
      const results = await Promise.allSettled(fetchPromises);
      
      // Process results and handle partial failures
      const successfulResults = [];
      const errors = [];
      
      results.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value.success) {
          successfulResults.push(result.value);
          retryCountRef.current = 0; // Reset retry count on success
        } else if (result.status === 'fulfilled' && !result.value.success) {
          errors.push(result.value.error);
        } else {
          errors.push(result.reason?.message || 'Unknown error');
        }
      });

      // If we have any successful results, update the data
      if (successfulResults.length > 0) {
        const { sensors, stats } = aggregateAndDeduplicateData(successfulResults);
        
        if (isComponentMountedRef.current) {
          setSensorData(sensors);
          setDataStats(stats);
          setLastUpdated(new Date());
          
          // If there were partial errors, show warning but don't block update
          if (errors.length > 0 && errors.length < results.length) {
            setError({
              type: 'warning',
              message: `Some data sources failed: ${errors.join(', ')}`,
              timestamp: new Date()
            });
          } else {
            setError(null);
          }
        }
      } else {
        // All requests failed
        throw new Error(`All data sources failed: ${errors.join(', ')}`);
      }

    } catch (err) {
      console.error('Sensor data fetch error:', err);
      
      if (isComponentMountedRef.current) {
        setError({
          type: 'error',
          message: err.message || 'Failed to fetch sensor data',
          timestamp: new Date()
        });

        // Implement exponential backoff for retries
        retryCountRef.current += 1;
        if (retryCountRef.current <= MAX_RETRY_ATTEMPTS) {
          const retryDelay = Math.min(ERROR_RETRY_INTERVAL * Math.pow(2, retryCountRef.current - 1), 300000);
          console.log(`Retrying in ${retryDelay}ms (attempt ${retryCountRef.current}/${MAX_RETRY_ATTEMPTS})`);
          
          setTimeout(() => {
            if (isComponentMountedRef.current) {
              fetchSensorData(true);
            }
          }, retryDelay);
        }
      }
    } finally {
      if (isComponentMountedRef.current && !isRetry) {
        setLoading(false);
      }
    }
  }, [bbox, enablePurpleAir, enableSensorCommunity, enableStoredData, aggregateAndDeduplicateData]);

  // Manual refresh function
  const refreshData = useCallback(() => {
    retryCountRef.current = 0;
    fetchSensorData(false);
  }, [fetchSensorData]);

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
        fetchSensorData(false);
      }
    }, fetchInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enableAutoRefresh, fetchInterval, fetchSensorData, loading]);

  // Initial data fetch on mount or when dependencies change
  useEffect(() => {
    isComponentMountedRef.current = true;
    fetchSensorData(false);

    return () => {
      isComponentMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchSensorData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isComponentMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Helper function to get sensors by source
  const getSensorsBySource = useCallback((source) => {
    return sensorData.filter(sensor => sensor.source === source);
  }, [sensorData]);

  // Helper function to get sensors within quality thresholds
  const getQualitySensors = useCallback((maxPM25 = 100) => {
    return sensorData.filter(sensor => 
      sensor.pm25 !== null && 
      sensor.pm25 !== undefined && 
      sensor.pm25 <= maxPM25
    );
  }, [sensorData]);

  return {
    // Data
    sensorData,
    dataStats,
    lastUpdated,
    
    // State
    loading,
    error,
    
    // Actions
    refreshData,
    getSensorsBySource,
    getQualitySensors,
    
    // Meta information
    isConnected: !error || error.type === 'warning',
    retryCount: retryCountRef.current
  };
};

export default useSensorData;