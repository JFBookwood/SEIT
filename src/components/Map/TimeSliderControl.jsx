import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  RotateCcw,
  Clock,
  Calendar
} from 'lucide-react';

function TimeSliderControl({ 
  currentTime = new Date(),
  onTimeChange,
  timeRange = { start: new Date(Date.now() - 24*60*60*1000), end: new Date() },
  isPlaying = false,
  onPlayToggle,
  playbackSpeed = 1,
  onSpeedChange,
  snapInterval = '1hour',
  onIntervalChange,
  availableTimestamps = [],
  onPrecomputeSnapshots
}) {
  const [localTime, setLocalTime] = useState(currentTime);
  const intervalRef = useRef(null);

  // Sync local time with prop
  useEffect(() => {
    setLocalTime(currentTime);
  }, [currentTime]);

  // Handle playback
  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        const nextTime = new Date(localTime.getTime() + getIntervalMs() * playbackSpeed);
        
        if (nextTime <= timeRange.end) {
          setLocalTime(nextTime);
          onTimeChange(nextTime);
        } else {
          onPlayToggle(); // Stop at end
        }
      }, 1000 / playbackSpeed); // Adjust animation speed
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPlaying, localTime, playbackSpeed, timeRange.end, onTimeChange, onPlayToggle]);

  const getIntervalMs = () => {
    switch (snapInterval) {
      case '30min': return 30 * 60 * 1000;
      case '1hour': return 60 * 60 * 1000;
      case '6hour': return 6 * 60 * 60 * 1000;
      case '1day': return 24 * 60 * 60 * 1000;
      default: return 60 * 60 * 1000;
    }
  };

  const snapToInterval = (time) => {
    const intervalMs = getIntervalMs();
    const snapped = new Date(Math.round(time.getTime() / intervalMs) * intervalMs);
    return snapped;
  };

  const handleTimeSliderChange = (e) => {
    const percentage = parseFloat(e.target.value);
    const timeRange_ms = timeRange.end.getTime() - timeRange.start.getTime();
    const newTime = new Date(timeRange.start.getTime() + (timeRange_ms * percentage / 100));
    const snappedTime = snapToInterval(newTime);
    
    setLocalTime(snappedTime);
    onTimeChange(snappedTime);
  };

  const handleStepBackward = () => {
    const newTime = new Date(localTime.getTime() - getIntervalMs());
    if (newTime >= timeRange.start) {
      setLocalTime(newTime);
      onTimeChange(newTime);
    }
  };

  const handleStepForward = () => {
    const newTime = new Date(localTime.getTime() + getIntervalMs());
    if (newTime <= timeRange.end) {
      setLocalTime(newTime);
      onTimeChange(newTime);
    }
  };

  const handleReset = () => {
    const resetTime = timeRange.end; // Reset to most recent time
    setLocalTime(resetTime);
    onTimeChange(resetTime);
  };

  const calculateSliderValue = () => {
    const timeRange_ms = timeRange.end.getTime() - timeRange.start.getTime();
    const currentOffset = localTime.getTime() - timeRange.start.getTime();
    return (currentOffset / timeRange_ms) * 100;
  };

  const speedOptions = [0.5, 1, 2, 4];

  return (
    <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-lg p-4 min-w-96">
      {/* Time Display */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Clock className="w-4 h-4 text-neutral-500" />
          <div>
            <div className="text-sm font-medium text-neutral-900 dark:text-white">
              {localTime.toLocaleDateString()} {localTime.toLocaleTimeString()}
            </div>
            <div className="text-xs text-neutral-500">
              UTC: {localTime.toISOString().replace('T', ' ').replace('.000Z', '')}
            </div>
          </div>
        </div>
        
        <button
          onClick={handleReset}
          className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 transition-colors"
          title="Reset to current time"
        >
          <RotateCcw className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
        </button>
      </div>

      {/* Playback Controls */}
      <div className="flex items-center space-x-2 mb-4">
        <button
          onClick={handleStepBackward}
          disabled={localTime <= timeRange.start}
          className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <SkipBack className="w-4 h-4" />
        </button>
        
        <button
          onClick={onPlayToggle}
          className="p-3 rounded-lg bg-primary-600 hover:bg-primary-700 text-white transition-colors"
        >
          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
        </button>
        
        <button
          onClick={handleStepForward}
          disabled={localTime >= timeRange.end}
          className="p-2 rounded-lg bg-neutral-100 dark:bg-neutral-700 hover:bg-neutral-200 dark:hover:bg-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <SkipForward className="w-4 h-4" />
        </button>

        {/* Speed Control */}
        <div className="flex items-center space-x-1 ml-4">
          <span className="text-xs text-neutral-500">Speed:</span>
          <select
            value={playbackSpeed}
            onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
            className="px-2 py-1 text-xs border border-neutral-300 dark:border-neutral-600 rounded bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
          >
            {speedOptions.map(speed => (
              <option key={speed} value={speed}>
                {speed}x
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Time Slider */}
      <div className="mb-4">
        <input
          type="range"
          min="0"
          max="100"
          step="0.1"
          value={calculateSliderValue()}
          onChange={handleTimeSliderChange}
          className="w-full h-2 bg-neutral-200 rounded-lg appearance-none cursor-pointer slider"
        />
        <div className="flex justify-between text-xs text-neutral-500 mt-1">
          <span>{timeRange.start.toLocaleDateString()}</span>
          <span>{timeRange.end.toLocaleDateString()}</span>
        </div>
      </div>

      {/* Interval Selection */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
          Time Step:
        </label>
        <select
          value={snapInterval}
          onChange={(e) => onIntervalChange(e.target.value)}
          className="px-2 py-1 text-xs border border-neutral-300 dark:border-neutral-600 rounded bg-white dark:bg-neutral-700 text-neutral-900 dark:text-white"
        >
          <option value="30min">30 Minutes</option>
          <option value="1hour">1 Hour</option>
          <option value="6hour">6 Hours</option>
          <option value="1day">1 Day</option>
        </select>
      </div>

      {/* Precompute Option */}
      {onPrecomputeSnapshots && (
        <div className="mt-4 pt-3 border-t border-neutral-200 dark:border-neutral-700">
          <button
            onClick={() => onPrecomputeSnapshots(24, 1)}
            className="w-full px-3 py-2 text-xs bg-primary-50 dark:bg-primary-900/20 hover:bg-primary-100 dark:hover:bg-primary-900/30 rounded-lg border border-primary-200 dark:border-primary-800 text-primary-600 transition-colors"
          >
            Precompute 24h Snapshots
          </button>
          <div className="text-xs text-neutral-500 mt-1 text-center">
            Improves animation smoothness
          </div>
        </div>
      )}

      {/* Available Data Info */}
      {availableTimestamps.length > 0 && (
        <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-700">
          <div className="text-xs text-neutral-500">
            <div className="flex justify-between">
              <span>Available Data:</span>
              <span className="font-medium">{availableTimestamps.length} timestamps</span>
            </div>
            <div className="flex justify-between">
              <span>Latest:</span>
              <span className="font-medium">
                {new Date(availableTimestamps[0]).toLocaleTimeString()}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TimeSliderControl;
