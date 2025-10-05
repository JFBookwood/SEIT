import React from 'react';
import { Target, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';

function CalibrationStatusCard({ calibrationData, onViewDetails }) {
  const getStatusIcon = (needsRecalibration, isActive) => {
    if (!isActive) return <AlertTriangle className="w-5 h-5 text-environmental-red" />;
    if (needsRecalibration) return <AlertTriangle className="w-5 h-5 text-environmental-yellow" />;
    return <CheckCircle className="w-5 h-5 text-environmental-green" />;
  };

  const getStatusColor = (needsRecalibration, isActive) => {
    if (!isActive) return 'text-environmental-red';
    if (needsRecalibration) return 'text-environmental-yellow';
    return 'text-environmental-green';
  };

  const getStatusText = (needsRecalibration, isActive) => {
    if (!isActive) return 'Inactive';
    if (needsRecalibration) return 'Needs Recalibration';
    return 'Active';
  };

  if (!calibrationData) {
    return (
      <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
        <div className="flex items-center space-x-3">
          <Target className="w-6 h-6 text-neutral-400" />
          <div>
            <h3 className="font-semibold text-neutral-900 dark:text-white">Calibration Status</h3>
            <p className="text-sm text-neutral-500">No calibration data available</p>
          </div>
        </div>
      </div>
    );
  }

  const { performance_stats, total_sensors, active_calibrations, recent_calibrations } = calibrationData;

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white">
          Calibration Overview
        </h3>
        <button
          onClick={onViewDetails}
          className="text-primary-600 hover:text-primary-700 text-sm font-medium transition-colors"
        >
          View Details →
        </button>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Sensors */}
        <div className="text-center">
          <div className="text-lg font-bold text-neutral-900 dark:text-white">
            {total_sensors || 0}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400">Total Sensors</div>
        </div>
        
        {/* Active Calibrations */}
        <div className="text-center">
          <div className="text-lg font-bold text-environmental-green">
            {active_calibrations || 0}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400">Active</div>
        </div>
        
        {/* Average R² */}
        <div className="text-center">
          <div className="text-lg font-bold text-primary-600">
            {performance_stats?.mean_r2?.toFixed(3) || 'N/A'}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400">Avg R²</div>
        </div>
        
        {/* Average Uncertainty */}
        <div className="text-center">
          <div className="text-lg font-bold text-environmental-yellow">
            {performance_stats?.mean_sigma_i?.toFixed(1) || 'N/A'}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400">Avg σᵢ (μg/m³)</div>
        </div>
      </div>
      
      {/* Quality Indicators */}
      <div className="mt-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center justify-between text-sm">
          <span className="text-neutral-600 dark:text-neutral-400">Recent Calibrations (30d):</span>
          <span className="font-medium text-neutral-900 dark:text-white">
            {recent_calibrations || 0}
          </span>
        </div>
        
        <div className="flex items-center justify-between text-sm mt-2">
          <span className="text-neutral-600 dark:text-neutral-400">High Quality (R² > 0.8):</span>
          <span className="font-medium text-environmental-green">
            {performance_stats?.high_quality_count || 0}
          </span>
        </div>
      </div>
    </div>
  );
}

export default CalibrationStatusCard;
