# MILESTONE 5: Frontend Enhancement & Visualization

## 🎯 OBJECTIVE
Professional time-series visualization with uncertainty and enhanced user experience.

## 📋 IMPLEMENTATION TASKS

### Task 5.1: Time Slider & History Controls
**Time: 60 minutes**

#### Time Navigation Component
```javascript
const TimeSliderControl = ({ currentTime, onTimeChange, timeRange, isPlaying, onPlayToggle }) => {
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, 4x
  const [snapInterval, setSnapInterval] = useState('1hour'); // 1hour, 6hour, 1day
  
  const handleTimeChange = (newTime) => {
    // Snap to nearest interval
    const snappedTime = snapToInterval(newTime, snapInterval);
    onTimeChange(snappedTime);
  };
  
  return (
    <div className="time-slider-container">
      <PlaybackControls 
        isPlaying={isPlaying}
        onPlayToggle={onPlayToggle}
        speed={playbackSpeed}
        onSpeedChange={setPlaybackSpeed}
      />
      <TimeSlider 
        currentTime={currentTime}
        timeRange={timeRange}
        onTimeChange={handleTimeChange}
        interval={snapInterval}
      />
      <IntervalSelector 
        interval={snapInterval}
        onIntervalChange={setSnapInterval}
      />
    </div>
  );
};
```

#### Efficient Data Loading
```javascript
const useTimeSeriesData = (bbox, timeRange, interval) => {
  const [snapshots, setSnapshots] = useState({});
  const [loading, setLoading] = useState(false);
  
  const loadSnapshot = useCallback(async (timestamp) => {
    const key = `${timestamp}_${bbox.join('_')}`;
    
    if (snapshots[key]) {
      return snapshots[key]; // Use cached snapshot
    }
    
    setLoading(true);
    try {
      const data = await api.getHeatmapGrid({
        ...bbox,
        timestamp,
        resolution: 250
      });
      
      setSnapshots(prev => ({
        ...prev,
        [key]: data
      }));
      
      return data;
    } finally {
      setLoading(false);
    }
  }, [bbox, snapshots]);
  
  return { snapshots, loadSnapshot, loading };
};
```

### Task 5.2: Uncertainty Visualization
**Time: 75 minutes**

#### Uncertainty Overlay Component
```javascript
const UncertaintyOverlay = ({ gridData, uncertaintyThreshold = 10, opacity = 0.6 }) => {
  const renderUncertaintyLayer = useCallback(() => {
    return gridData.features.map(feature => {
      const uncertainty = feature.properties.uncertainty;
      const isHighUncertainty = uncertainty > uncertaintyThreshold;
      
      return (
        <GridCell
          key={feature.id}
          coordinates={feature.geometry.coordinates}
          value={feature.properties.c_hat}
          uncertainty={uncertainty}
          style={{
            fillOpacity: isHighUncertainty ? opacity * 0.3 : opacity,
            strokeWidth: isHighUncertainty ? 2 : 0,
            strokePattern: isHighUncertainty ? 'diagonal-hatch' : 'none'
          }}
        />
      );
    });
  }, [gridData, uncertaintyThreshold, opacity]);
  
  return <div className="uncertainty-overlay">{renderUncertaintyLayer()}</div>;
};
```

#### Method Toggle Controls
```javascript
const InterpolationMethodToggle = ({ currentMethod, onMethodChange, available = ['idw', 'kriging'] }) => {
  return (
    <div className="method-toggle">
      <label className="text-sm font-medium">Interpolation Method:</label>
      <div className="flex space-x-2 mt-1">
        {available.map(method => (
          <button
            key={method}
            onClick={() => onMethodChange(method)}
            className={`px-3 py-1 text-xs rounded ${
              currentMethod === method 
                ? 'bg-primary-600 text-white' 
                : 'bg-neutral-200 text-neutral-700'
            }`}
          >
            {method.toUpperCase()}
          </button>
        ))}
      </div>
      
      {currentMethod === 'kriging' && (
        <div className="mt-2 text-xs text-neutral-500">
          Includes NASA satellite and meteorological covariates
        </div>
      )}
    </div>
  );
};
```

### Task 5.3: Enhanced Sensor Popups
**Time: 45 minutes**

#### Comprehensive Sensor Display
```javascript
const EnhancedSensorPopup = ({ sensor, calibration, onDetailView }) => {
  const {
    sensor_id,
    pm25_raw,
    pm25_corrected,
    sigma_i,
    last_updated_utc,
    sensor_type,
    qc_flags
  } = sensor;
  
  return (
    <div className="sensor-popup max-w-sm">
      <div className="popup-header">
        <h3 className="font-semibold">{sensor_type} Sensor {sensor_id}</h3>
        <QualityBadge flags={qc_flags} />
      </div>
      
      <div className="measurements-grid">
        <MeasurementRow 
          label="PM2.5 (Corrected)"
          value={pm25_corrected}
          unit="μg/m³"
          uncertainty={sigma_i}
          highlight={true}
        />
        <MeasurementRow 
          label="PM2.5 (Raw)"
          value={pm25_raw}
          unit="μg/m³"
          className="text-neutral-500"
        />
        
        <div className="metadata-section">
          <div className="text-xs text-neutral-500">
            Updated: {formatTimestamp(last_updated_utc)}
          </div>
          <div className="text-xs text-neutral-500">
            Uncertainty: ±{sigma_i?.toFixed(1)} μg/m³
          </div>
        </div>
      </div>
      
      <div className="popup-actions">
        <button 
          onClick={() => onDetailView(sensor)}
          className="text-primary-600 text-sm"
        >
          View History →
        </button>
      </div>
    </div>
  );
};
```

## 🎨 VISUAL DESIGN SPECIFICATIONS

### Heatmap Color Scale
```javascript
const PM25_COLOR_SCALE = [
  { threshold: 0,   color: '#10b981', label: 'Good' },
  { threshold: 12,  color: '#f59e0b', label: 'Moderate' },
  { threshold: 35,  color: '#ef4444', label: 'Unhealthy for Sensitive' },
  { threshold: 55,  color: '#dc2626', label: 'Unhealthy' },
  { threshold: 150, color: '#991b1b', label: 'Very Unhealthy' }
];
```

### Uncertainty Visualization
- **Low Uncertainty**: Full opacity, solid colors
- **Medium Uncertainty**: Reduced opacity (70%)
- **High Uncertainty**: Hatched pattern overlay, reduced opacity (40%)
- **No Data**: Transparent with subtle border

### Time Controls Design
- **Compact Controls**: Minimalist play/pause/speed controls
- **Smooth Slider**: Snapping to available time intervals
- **Progress Indicator**: Visual feedback during data loading
- **Timestamp Display**: Clear UTC timestamp with local conversion

## ✅ ACCEPTANCE CRITERIA

### Time Navigation
- [ ] Time slider smoothly navigating hourly snapshots
- [ ] Play/pause animation with configurable speed
- [ ] Proper loading states during time transitions
- [ ] Timestamp validation and snapping to available data

### Heatmap Visualization
- [ ] IDW and kriging layers rendering correctly
- [ ] Color scale accurately reflecting PM2.5 concentrations
- [ ] Uncertainty overlay providing meaningful visual feedback
- [ ] Toggle between interpolation methods working smoothly

### Sensor Information
- [ ] Popups showing corrected values with uncertainty
- [ ] Quality flags visually indicated
- [ ] Calibration status clearly communicated
- [ ] Links to detailed sensor history functional

### Performance
- [ ] Map interactions remain smooth during heatmap updates
- [ ] Time navigation responsive with cached snapshots
- [ ] Memory usage stable during extended use
- [ ] Visual quality maintained across zoom levels
