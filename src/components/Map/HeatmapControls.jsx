import React, { useState } from 'react';
import { 
  Layers, 
  Settings, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  Sliders3,
  Info
} from 'lucide-react';

function HeatmapControls({ 
  isVisible = true,
  opacity = 0.7,
  resolution = 250,
  method = 'idw',
  showUncertainty = true,
  loading = false,
  onVisibilityToggle,
  onOpacityChange,
  onResolutionChange,
  onMethodChange,
  onUncertaintyToggle,
  onRefresh,
  sensorCount = 0
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  const resolutionOptions = [
    { value: 100, label: '100m (High Detail)', maxArea: 'Small areas only' },
    { value: 250, label: '250m (Default)', maxArea: 'Recommended' },
    { value: 500, label: '500m (Performance)', maxArea: 'Large areas' },
    { value: 1000, label: '1km (Overview)', maxArea: 'Very large areas' }
  ];

  const methodOptions = [
    { value: 'idw', label: 'IDW', description: 'Fast & reliable' }
  ];

  return (
    <div className="absolute top-16 right-4 z-30 bg-white dark:bg-neutral-800 rounded-lg shadow-lg border border-neutral-200 dark:border-neutral-700">
      {/* Header Controls */}
      <div className="flex items-center justify-between p-3 border-b border-neutral-200 dark:border-neutral-700">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-primary-600" />
          <span className="text-sm font-medium text-neutral-900 dark:text-white">
            PM2.5 Heatmap
          </span>
          {loading && (
            <RefreshCw className="w-3 h-3 text-primary-600 animate-spin" />
          )}
        </div>
        
        <div className="flex items-center space-x-1">
          <button
            onClick={onRefresh}
            className="p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
            disabled={loading}
            title="Refresh heatmap"
          >
            <RefreshCw className={`w-4 h-4 text-neutral-600 dark:text-neutral-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
          
          <button
            onClick={onVisibilityToggle}
            className="p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
            title={isVisible ? 'Hide heatmap' : 'Show heatmap'}
          >
            {isVisible ? (
              <Eye className="w-4 h-4 text-primary-600" />
            ) : (
              <EyeOff className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
            )}
          </button>
          
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
            title="Toggle settings"
          >
            <Sliders3 className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
          </button>
        </div>
      </div>

      {/* Expanded Controls */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* Opacity Control */}
          <div>
            <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Opacity: {Math.round(opacity * 100)}%
            </label>
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.1"
              value={opacity}
              onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
              className="w-full h-2 bg-neutral-200 rounded appearance-none cursor-pointer"
            />
          </div>

          {/* Resolution Control */}
          <div>
            <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Grid Resolution
            </label>
            <select
              value={resolution}
              onChange={(e) => onResolutionChange(parseInt(e.target.value))}
              className="w-full px-3 py-2 text-xs border border-neutral-300 dark:border-neutral-600 rounded-md bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
            >
              {resolutionOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <div className="text-xs text-neutral-400 mt-1">
              Current: {resolution}m grid
            </div>
          </div>

          {/* Method Selection */}
          <div>
            <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-2">
              Interpolation Method
            </label>
            <div className="space-y-2">
              {methodOptions.map(option => (
                <label key={option.value} className="flex items-center space-x-2">
                  <input
                    type="radio"
                    name="method"
                    value={option.value}
                    checked={method === option.value}
                    onChange={(e) => onMethodChange(e.target.value)}
                    className="w-3 h-3 text-primary-600 border-neutral-300 dark:border-neutral-600 focus:ring-primary-500"
                  />
                  <div className="flex-1">
                    <div className="text-xs text-neutral-900 dark:text-white">
                      {option.label}
                    </div>
                    <div className="text-xs text-neutral-500">
                      {option.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Uncertainty Toggle */}
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
              Show Uncertainty
            </label>
            <button
              onClick={onUncertaintyToggle}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                showUncertainty ? 'bg-primary-600' : 'bg-neutral-200 dark:bg-neutral-700'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  showUncertainty ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Status Display */}
          {sensorCount > 0 && (
            <div className="pt-3 border-t border-neutral-200 dark:border-neutral-700">
              <div className="flex items-center space-x-1 mb-2">
                <Info className="w-3 h-3 text-neutral-500" />
                <span className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                  Heatmap Info
                </span>
              </div>
              
              <div className="space-y-1 text-xs text-neutral-600 dark:text-neutral-400">
                <div className="flex justify-between">
                  <span>Sensors Used:</span>
                  <span className="font-medium">{sensorCount}</span>
                </div>
                <div className="flex justify-between">
                  <span>Method:</span>
                  <span className="font-medium">{method.toUpperCase()}</span>
                </div>
                <div className="flex justify-between">
                  <span>Resolution:</span>
                  <span className="font-medium">{resolution}m</span>
                </div>
                <div className="flex justify-between">
                  <span>Status:</span>
                  <span className={`font-medium ${loading ? 'text-yellow-500' : 'text-green-500'}`}>
                    {loading ? 'Generating...' : 'Ready'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

   </div>
  );
}

export default HeatmapControls;
