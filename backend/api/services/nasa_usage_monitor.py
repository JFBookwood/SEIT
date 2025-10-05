import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import os

logger = logging.getLogger(__name__)

class NASAUsageMonitor:
    """Monitor and analyze NASA API usage patterns for compliance and optimization"""
    
    def __init__(self):
        self.daily_usage_cache = defaultdict(list)
        self.rate_tracking = defaultdict(deque)
        
        # Usage thresholds and limits
        self.usage_limits = {
            'daily_request_limit': 10000,  # Conservative daily limit
            'hourly_request_limit': 500,   # Conservative hourly limit
            'requests_per_minute': 60,     # 1 request per second max
            'concurrent_requests': 10      # Max concurrent requests
        }
        
        # Service-specific monitoring
        self.service_configs = {
            'cmr': {'weight': 1, 'priority': 'high'},
            'gibs': {'weight': 0.5, 'priority': 'medium'},
            'harmony': {'weight': 3, 'priority': 'high'},
            'urs': {'weight': 0.1, 'priority': 'low'}
        }
    
    def record_api_call(self, service: str, endpoint: str, status_code: int, 
                       duration_ms: float, response_size: int = 0):
        """Record API call for usage monitoring"""
        timestamp = datetime.now(timezone.utc)
        
        usage_record = {
            'timestamp': timestamp.isoformat(),
            'service': service,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'response_size_bytes': response_size,
            'success': 200 <= status_code < 300,
            'weight': self.service_configs.get(service, {}).get('weight', 1)
        }
        
        # Add to daily cache
        date_key = timestamp.strftime('%Y-%m-%d')
        self.daily_usage_cache[date_key].append(usage_record)
        
        # Add to rate tracking (last 60 seconds)
        minute_key = timestamp.strftime('%Y-%m-%d %H:%M')
        self.rate_tracking[minute_key].append(usage_record)
        
        # Clean old rate tracking data
        self._cleanup_rate_tracking()
        
        # Check for usage warnings
        self._check_usage_warnings(service, timestamp)
        
        logger.debug(f"NASA API usage recorded: {service}/{endpoint} -> {status_code} ({duration_ms:.1f}ms)")
    
    def get_current_rate_status(self) -> Dict[str, Any]:
        """Get current rate limiting status"""
        now = datetime.now(timezone.utc)
        
        # Count requests in last minute
        requests_last_minute = 0
        minute_key = now.strftime('%Y-%m-%d %H:%M')
        
        if minute_key in self.rate_tracking:
            requests_last_minute = len(self.rate_tracking[minute_key])
        
        # Count requests in last hour
        requests_last_hour = 0
        for i in range(60):  # Last 60 minutes
            check_time = now - timedelta(minutes=i)
            hour_key = check_time.strftime('%Y-%m-%d %H:%M')
            if hour_key in self.rate_tracking:
                requests_last_hour += len(self.rate_tracking[hour_key])
        
        # Calculate usage percentages
        minute_usage_pct = (requests_last_minute / self.usage_limits['requests_per_minute']) * 100
        hour_usage_pct = (requests_last_hour / self.usage_limits['hourly_request_limit']) * 100
        
        return {
            'requests_last_minute': requests_last_minute,
            'requests_last_hour': requests_last_hour,
            'minute_limit': self.usage_limits['requests_per_minute'],
            'hour_limit': self.usage_limits['hourly_request_limit'],
            'minute_usage_percent': round(minute_usage_pct, 1),
            'hour_usage_percent': round(hour_usage_pct, 1),
            'rate_status': self._get_rate_status(minute_usage_pct, hour_usage_pct),
            'timestamp': now.isoformat()
        }
    
    def get_usage_analytics(self, days_back: int = 7) -> Dict[str, Any]:
        """Generate comprehensive usage analytics"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        analytics = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days_back
            },
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_data_transferred_mb': 0,
            'average_response_time_ms': 0,
            'service_breakdown': defaultdict(int),
            'endpoint_breakdown': defaultdict(int),
            'hourly_patterns': defaultdict(int),
            'error_analysis': defaultdict(int),
            'daily_trends': []
        }
        
        total_duration = 0
        all_response_times = []
        
        # Analyze daily usage cache
        for i in range(days_back):
            check_date = end_date - timedelta(days=i)
            date_key = check_date.strftime('%Y-%m-%d')
            
            if date_key in self.daily_usage_cache:
                daily_records = self.daily_usage_cache[date_key]
                
                daily_total = len(daily_records)
                daily_successful = sum(1 for r in daily_records if r['success'])
                daily_failed = daily_total - daily_successful
                daily_data_mb = sum(r.get('response_size_bytes', 0) for r in daily_records) / (1024 * 1024)
                
                analytics['daily_trends'].append({
                    'date': date_key,
                    'total_requests': daily_total,
                    'successful_requests': daily_successful,
                    'failed_requests': daily_failed,
                    'data_transferred_mb': round(daily_data_mb, 2),
                    'success_rate': (daily_successful / daily_total * 100) if daily_total > 0 else 0
                })
                
                # Process individual records
                for record in daily_records:
                    analytics['total_requests'] += 1
                    
                    if record['success']:
                        analytics['successful_requests'] += 1
                    else:
                        analytics['failed_requests'] += 1
                        analytics['error_analysis'][record['status_code']] += 1
                    
                    # Service and endpoint breakdown
                    analytics['service_breakdown'][record['service']] += 1
                    analytics['endpoint_breakdown'][record['endpoint']] += 1
                    
                    # Response time tracking
                    if record.get('duration_ms'):
                        total_duration += record['duration_ms']
                        all_response_times.append(record['duration_ms'])
                    
                    # Data transfer tracking
                    if record.get('response_size_bytes'):
                        analytics['total_data_transferred_mb'] += record['response_size_bytes'] / (1024 * 1024)
                    
                    # Hourly patterns
                    hour = datetime.fromisoformat(record['timestamp']).hour
                    analytics['hourly_patterns'][hour] += 1
        
        # Calculate averages and percentiles
        analytics['average_response_time_ms'] = total_duration / analytics['total_requests'] if analytics['total_requests'] > 0 else 0
        analytics['success_rate'] = (analytics['successful_requests'] / analytics['total_requests'] * 100) if analytics['total_requests'] > 0 else 0
        analytics['total_data_transferred_mb'] = round(analytics['total_data_transferred_mb'], 2)
        
        if all_response_times:
            analytics['response_time_percentiles'] = {
                'p50': float(np.percentile(all_response_times, 50)),
                'p90': float(np.percentile(all_response_times, 90)),
                'p95': float(np.percentile(all_response_times, 95)),
                'p99': float(np.percentile(all_response_times, 99))
            }
        
        # Convert defaultdicts to regular dicts
        analytics['service_breakdown'] = dict(analytics['service_breakdown'])
        analytics['endpoint_breakdown'] = dict(analytics['endpoint_breakdown'])
        analytics['hourly_patterns'] = dict(analytics['hourly_patterns'])
        analytics['error_analysis'] = dict(analytics['error_analysis'])
        
        return analytics
    
    def _cleanup_rate_tracking(self):
        """Remove old entries from rate tracking"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=2)  # Keep 2 hours of data
        
        keys_to_remove = []
        for time_key in self.rate_tracking.keys():
            try:
                key_time = datetime.strptime(time_key, '%Y-%m-%d %H:%M')
                key_time = key_time.replace(tzinfo=timezone.utc)
                if key_time < cutoff_time:
                    keys_to_remove.append(time_key)
            except Exception:
                keys_to_remove.append(time_key)  # Remove malformed keys
        
        for key in keys_to_remove:
            del self.rate_tracking[key]
    
    def _check_usage_warnings(self, service: str, timestamp: datetime):
        """Check for usage patterns that might need attention"""
        rate_status = self.get_current_rate_status()
        
        # Warn if approaching limits
        if rate_status['minute_usage_percent'] > 80:
            logger.warning(f"High NASA API usage: {rate_status['minute_usage_percent']:.1f}% of minute limit")
        
        if rate_status['hour_usage_percent'] > 70:
            logger.warning(f"High NASA API usage: {rate_status['hour_usage_percent']:.1f}% of hourly limit")
        
        # Check for error patterns
        date_key = timestamp.strftime('%Y-%m-%d')
        if date_key in self.daily_usage_cache:
            recent_records = self.daily_usage_cache[date_key][-10:]  # Last 10 requests
            recent_failures = sum(1 for r in recent_records if not r['success'])
            
            if recent_failures >= 5:
                logger.error(f"High failure rate for NASA {service} API: {recent_failures}/10 recent requests failed")
    
    def _get_rate_status(self, minute_pct: float, hour_pct: float) -> str:
        """Determine rate limiting status"""
        if minute_pct >= 90 or hour_pct >= 90:
            return 'critical'
        elif minute_pct >= 70 or hour_pct >= 70:
            return 'warning'
        elif minute_pct >= 50 or hour_pct >= 50:
            return 'moderate'
        else:
            return 'normal'

# Singleton instance
nasa_usage_monitor = NASAUsageMonitor()
