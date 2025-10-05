import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Layout/Navbar';
import ControlSidebar from './components/Sidebar/ControlSidebar';
import EnhancedMapContainer from './components/Map/EnhancedMapContainer';
import SensorDetailPanel from './components/DetailPanel/SensorDetailPanel';
import DashboardOverview from './components/Dashboard/DashboardOverview';
import ErrorBoundary from './components/Feedback/ErrorBoundary';
import StatusIndicator from './components/Feedback/StatusIndicator';
import LoadingOverlay from './components/Feedback/LoadingOverlay';
import NotificationToast from './components/Feedback/NotificationToast';
import DataSourceStatus from './components/Dashboard/DataSourceStatus';
import Dashboard from './pages/Dashboard';
import Maps from './pages/Maps';
import Analytics from './pages/Analytics';
import Reports from './pages/Reports';
import Admin from './pages/Admin';
import useSensorData from './hooks/useSensorData';
import useEnhancedSensorData from './hooks/useEnhancedSensorData';
import useNotifications from './hooks/useNotifications';

function App() {
  const [darkMode, setDarkMode] = useState(false);
  const [mapBounds, setMapBounds] = useState(null); // Global coverage - no restrictions
  const [currentView, setCurrentView] = useState('dashboard'); // Define currentView

  // Enhanced sensor data management with real-time updates
  const legacySensorData = useSensorData({
    bbox: mapBounds,
    enableAutoRefresh: false, // Disable legacy system
    fetchInterval: 60000,
    enablePurpleAir: true,
    enableSensorCommunity: true,
    enableStoredData: false
  });

  // Enhanced multi-source sensor data management
  const {
    sensorData,
    weatherData,
    satelliteData,
    enhancedStats,
    lastUpdated,
    loading,
    error,
    refreshEnhancedData,
    getSensorsBySource,
    getSensorsByPollutionLevel,
    getHighQualitySensors,
    isConnected,
    retryCount,
    dataSourcesActive
  } = useEnhancedSensorData({
    bbox: mapBounds,
    enableAutoRefresh: true,
    fetchInterval: 30000, // 30 seconds
    enablePurpleAir: true,
    enableSensorCommunity: true,
    enableOpenAQ: true,
    enableWeather: true,
    enableSatellite: currentView === 'map' // Only load satellite data for map view
  });

  // Notification system
  const {
    notifications,
    removeNotification,
    showSuccess,
    showError,
    showWarning,
    showInfo
  } = useNotifications();

  // Make notification functions globally available
  useEffect(() => {
    window.showSuccess = showSuccess;
    window.showError = showError;
    window.showWarning = showWarning;
    window.showInfo = showInfo;
    
    return () => {
      delete window.showSuccess;
      delete window.showError;
      delete window.showWarning;
      delete window.showInfo;
    };
  }, [showSuccess, showError, showWarning, showInfo]);

  // Initialize dark mode from localStorage
  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode) {
      setDarkMode(JSON.parse(savedDarkMode));
    }
  }, []);

  // Apply dark mode class to document
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
  }, [darkMode]);

  // Handle data loading notifications
  useEffect(() => {
    if (error?.type === 'error' && enhancedStats.total === 0) {
      showError(error.message, {
        title: 'Data Loading Error',
        actions: [
          {
            label: 'Retry',
            handler: refreshEnhancedData,
            primary: true
          }
        ]
      });
    } else if (error?.type === 'warning' && enhancedStats.total === 0) {
      showWarning(error.message, {
        title: 'Data Notice'
      });
    } else if (error?.type === 'info') {
      // Don't show info messages as errors
      console.log('Info:', error.message);
    }
  }, [error, showError, showWarning, refreshEnhancedData, enhancedStats.total]);
  // Show success notification on successful data refresh
  useEffect(() => {
    if (lastUpdated && !loading && enhancedStats.total > 0) {
      const activeSources = Object.keys(enhancedStats).filter(key => 
        !['total', 'errors', 'coverage', 'averageValues'].includes(key) && enhancedStats[key] > 0
      ).length;
      
      // Only show success for first load or if we have real data
      const isFirstLoad = sensorData.length > 0 && !sessionStorage.getItem('seit_first_load');
      if (isFirstLoad) {
        sessionStorage.setItem('seit_first_load', 'true');
        const message = `Loaded ${enhancedStats.total} sensors from ${activeSources} sources`;
        showSuccess(message, {
          title: 'Data Loaded Successfully',
          autoHide: true
        });
      }
    }
  }, [lastUpdated, loading, enhancedStats, showSuccess, sensorData.length]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return (
    <ErrorBoundary>
      <Router>
      <div className="min-h-screen bg-neutral-50 dark:bg-space-900">
        <Navbar darkMode={darkMode} toggleDarkMode={toggleDarkMode} />
        
          <main className="pt-16">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/maps" element={<Maps />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/admin" element={<Admin />} />
            </Routes>
          </main>
       
        {/* Notification System */}
        <NotificationToast
          notifications={notifications}
          onDismiss={removeNotification}
          maxVisible={3}
          autoHideDuration={5000}
        />
        
        {/* Footer */}
        <footer className="border-t border-neutral-200 dark:border-neutral-700 bg-white dark:bg-space-900">
          <div className="max-w-7xl mx-auto px-6 py-3">
            <div className="text-center text-sm text-neutral-600 dark:text-neutral-400">
              AI vibe coded development by{' '}
              <a 
                href="https://biela.dev/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-primary-600 hover:text-primary-700 transition-colors"
              >
                Biela.dev
              </a>
              , powered by{' '}
              <a 
                href="https://teachmecode.ae/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-primary-600 hover:text-primary-700 transition-colors"
              >
                TeachMeCode® Institute
              </a>
            </div>
          </div>
        </footer>
      </div>
    </Router>
    </ErrorBoundary>
  );
}

export default App;