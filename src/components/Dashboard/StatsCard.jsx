import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

function StatsCard({ 
  title, 
  value, 
  unit = '', 
  trend = null, 
  trendValue = null,
  color = 'primary',
  icon: Icon,
  className = ''
}) {
  const colorClasses = {
    primary: 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400',
    green: 'bg-environmental-green/10 text-environmental-green',
    yellow: 'bg-environmental-yellow/10 text-environmental-yellow',
    red: 'bg-environmental-red/10 text-environmental-red',
    neutral: 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400'
  };
  
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4" />;
    if (trend === 'down') return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  };
  
  const getTrendColor = () => {
    if (trend === 'up') return 'text-environmental-red';
    if (trend === 'down') return 'text-environmental-green';
    return 'text-neutral-500';
  };
  
  return (
    <div className={`bg-white dark:bg-space-900 rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
            {title}
          </p>
          <div className="flex items-baseline space-x-1">
            <p className="text-2xl font-semibold text-neutral-900 dark:text-white">
              {value}
            </p>
            {unit && (
              <span className="text-sm text-neutral-500 dark:text-neutral-400">
                {unit}
              </span>
            )}
          </div>
          
          {trend && trendValue && (
            <div className={`flex items-center space-x-1 mt-2 ${getTrendColor()}`}>
              {getTrendIcon()}
              <span className="text-sm font-medium">
                {trendValue}
              </span>
              <span className="text-xs text-neutral-500 dark:text-neutral-400">
                vs last period
              </span>
            </div>
          )}
        </div>
        
        {Icon && (
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="w-6 h-6" />
          </div>
        )}
      </div>
    </div>
  );
}

export default StatsCard;
