import { useState, useEffect, useCallback, useRef } from 'react';
import { heatmapAPI } from '../services/heatmapApi';

const DEFAULT_RESOLUTION = 250; // 250m default resolution
const DEFAULT_METHOD = 'idw';

export const useHeatmapData = (options = {}) => {
  const {
    bbox = null,
    resolution = DEFAULT_RESOLUTION,
    method = DEFAULT_METHOD,
    timestamp = null,
    enableAutoRefresh = false,
    refreshInterval = 30000 // 30 seconds
  } = options;

  // State management
  const [heatmapData, setHeatmapData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [processingStats, setProcessingStats] = useState(null);

  // Refs for cleanup
  const intervalRef = useRef(null);
  const isComponentMountedRef = useRef(true);

  // Fetch heatmap grid data
  const fetchHeatmapData = useCallback(async (forceRefresh = false) => {
    if (!bbox || !isComponentMountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      const params = {
        west: bbox[0],
        south: bbox[1],
        east: bbox[2],
        north: bbox[3],
        resolution,
        method,
        force_refresh: forceRefresh
      };

      if (timestamp) {
        params.timestamp = timestamp;
      }

      const response = await heatmapAPI.getHeatmapGrid(params);

      if (response.success && isComponentMountedRef.current) {
        setHeatmapData(response.data);
        setLastUpdated(new Date());
        setProcessingStats(response.data.processing);
        
        // Update metadata if not set
        if (!metadata && response.data.metadata) {
          setMetadata(response.data.metadata);
        }
      } else {
        throw new Error(response.error || 'Failed to fetch heatmap data');
      }

    } catch (err) {
      console.error('Heatmap data fetch error:', err);
      
      if (isComponentMountedRef.current) {
        setError({
          type: 'error',
          message: err.message || 'Failed to generate heatmap',
          timestamp: new Date()
        });
      }
    } finally {
      if (isComponentMountedRef.current) {
        setLoading(false);
      }
    }
  }, [bbox, resolution, method, timestamp, metadata]);

  // Fetch metadata for current area
  const fetchMetadata = useCallback(async () => {
    if (!bbox) return;

    try {
      const response = await heatmapAPI.getHeatmapMetadata(bbox);
      
      if (response.success) {
        setMetadata(response.data);
      }
    } catch (err) {
      console.error('Metadata fetch error:', err);
    }
  }, [bbox]);

  // Precompute snapshots for smooth animation
  const precomputeSnapshots = useCallback(async (hoursBack = 24, intervalHours = 1) => {
    if (!bbox) return;

    try {
      const bboxString = bbox.join(',');
      const response = await heatmapAPI.precomputeSnapshots(bboxString, {
        resolution,
        hours_back: hoursBack,
        interval_hours: intervalHours
      });

      if (response.success) {
        console.log('Snapshots precomputed:', response.data);
        return response.data;
      } else {
        throw new Error(response.error);
      }
    } catch (err) {
      console.error('Snapshot precomputation failed:', err);
      throw err;
    }
  }, [bbox, resolution]);

  // Manual refresh
  const refreshHeatmapData = useCallback(() => {
    fetchHeatmapData(true);
  }, [fetchHeatmapData]);

  // Clear cache
  const clearCache = useCallback(async () => {
    try {
      const bboxString = bbox ? bbox.join(',') : null;
      const response = await heatmapAPI.clearCache({ bbox: bboxString });
      
      if (response.success) {
        // Refresh data after cache clear
        fetchHeatmapData(true);
        return response.data;
      } else {
        throw new Error(response.error);
      }
    } catch (err) {
      console.error('Cache clear failed:', err);
      throw err;
    }
  }, [bbox, fetchHeatmapData]);

  // Set up auto-refresh
  useEffect(() => {
    if (!enableAutoRefresh) return;

    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    intervalRef.current = setInterval(() => {
      if (isComponentMountedRef.current && !loading) {
        fetchHeatmapData(false);
      }
    }, refreshInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enableAutoRefresh, refreshInterval, fetchHeatmapData, loading]);

  // Initial data fetch and metadata
  useEffect(() => {
    isComponentMountedRef.current = true;
    
    if (bbox) {
      fetchMetadata();
      fetchHeatmapData(false);
    }

    return () => {
      isComponentMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [bbox, resolution, method, timestamp, fetchHeatmapData, fetchMetadata]);

  // Helper functions
  const getColorScale = useCallback(() => {
    return [
      { value: 0, color: '#10b981', label: 'Good' },
      { value: 12, color: '#f59e0b', label: 'Moderate' },
      { value: 35, color: '#ef4444', label: 'Unhealthy for Sensitive' },
      { value: 55, color: '#dc2626', label: 'Unhealthy' },
      { value: 150, color: '#991b1b', label: 'Very Unhealthy' }
    ];
  }, []);

  const getInterpolationInfo = useCallback(() => {
    if (!metadata) return null;

    return {
      method: metadata.interpolation_method,
      resolution_m: metadata.grid_resolution_m,
      search_radius_m: metadata.search_radius_m,
      sensors_used: metadata.sensors_used,
      processing_stats: metadata.processing_stats
    };
  }, [metadata]);

  return {
    // Data
    heatmapData,
    metadata,
    processingStats,
    lastUpdated,
    
    // State
    loading,
    error,
    
    // Actions
    refreshHeatmapData,
    precomputeSnapshots,
    clearCache,
    
    // Helpers
    getColorScale,
    getInterpolationInfo,
    
    // Configuration
    currentResolution: resolution,
    currentMethod: method,
    isConnected: !error || error.type === 'warning'
  };
};

export default useHeatmapData;
