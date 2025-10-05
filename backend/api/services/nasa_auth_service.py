import os
import logging
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from jose import jwt
import base64

from .redis_cache_service import cache_service

logger = logging.getLogger(__name__)

class NASAAuthService:
    """Secure NASA Earthdata authentication and token management service"""
    
    def __init__(self):
        # Load token from environment (server-side only)
        self.earthdata_token = os.getenv("NASA_EARTHDATA_TOKEN")
        self.earthdata_username = os.getenv("EARTHDATA_USERNAME")
        self.earthdata_password = os.getenv("EARTHDATA_PASSWORD")
        
        # NASA API endpoints
        self.urs_base_url = "https://urs.earthdata.nasa.gov"
        self.cmr_base_url = "https://cmr.earthdata.nasa.gov"
        self.gibs_base_url = "https://gibs.earthdata.nasa.gov"
        
        # Token metadata
        self.token_metadata = None
        
        if not self.earthdata_token:
            logger.warning("NASA_EARTHDATA_TOKEN not configured - NASA services will be limited")
        else:
            self.token_metadata = self._parse_token_metadata()
    
    def _parse_token_metadata(self) -> Optional[Dict]:
        """Parse JWT token to extract metadata and expiration"""
        try:
            if not self.earthdata_token:
                return None
            
            # JWT has 3 parts: header.payload.signature
            parts = self.earthdata_token.split('.')
            if len(parts) != 3:
                logger.error("Invalid JWT token format")
                return None
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded_bytes)
            
            # Extract key information
            metadata = {
                'user_id': token_data.get('uid'),
                'user_type': token_data.get('type'),
                'issued_at': datetime.fromtimestamp(token_data.get('iat', 0), tz=timezone.utc),
                'expires_at': datetime.fromtimestamp(token_data.get('exp', 0), tz=timezone.utc),
                'issuer': token_data.get('iss'),
                'identity_provider': token_data.get('identity_provider'),
                'assurance_level': token_data.get('assurance_level')
            }
            
            logger.info(f"NASA token parsed: User {metadata['user_id']}, expires {metadata['expires_at']}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to parse NASA token: {e}")
            return None
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for NASA API requests"""
        if not self.earthdata_token:
            raise ValueError("NASA Earthdata token not configured")
        
        return {
            "Authorization": f"Bearer {self.earthdata_token}",
            "Content-Type": "application/json",
            "User-Agent": "SEIT/1.0 (+https://seit.biela.dev)"
        }
    
    async def validate_token(self) -> Dict[str, Any]:
        """Validate NASA token against URS endpoint"""
        validation_result = {
            'valid': False,
            'token_configured': bool(self.earthdata_token),
            'metadata': self.token_metadata,
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'errors': []
        }
        
        if not self.earthdata_token:
            validation_result['errors'].append('NASA_EARTHDATA_TOKEN not configured')
            return validation_result
        
        try:
            # Check token expiration first
            if self.token_metadata:
                now = datetime.now(timezone.utc)
                expires_at = self.token_metadata['expires_at']
                
                if now >= expires_at:
                    validation_result['errors'].append(f'Token expired at {expires_at.isoformat()}')
                    return validation_result
                
                # Warn if token expires soon (within 7 days)
                days_until_expiry = (expires_at - now).days
                if days_until_expiry <= 7:
                    validation_result['warnings'] = [f'Token expires in {days_until_expiry} days']
            
            # Test token against URS profile endpoint
            headers = self.get_auth_headers()
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.urs_base_url}/api/users/user"
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        validation_result.update({
                            'valid': True,
                            'user_info': {
                                'uid': user_data.get('uid'),
                                'first_name': user_data.get('first_name'),
                                'last_name': user_data.get('last_name'),
                                'email': user_data.get('email_address'),
                                'country': user_data.get('country'),
                                'study_area': user_data.get('study_area')
                            },
                            'token_status': 'valid'
                        })
                        
                        logger.info(f"NASA token validated successfully for user {user_data.get('uid')}")
                        
                    elif response.status == 401:
                        validation_result['errors'].append('Token authentication failed - invalid or expired')
                        logger.error("NASA token authentication failed")
                        
                    else:
                        validation_result['errors'].append(f'URS validation failed with status {response.status}')
                        logger.error(f"URS validation failed: {response.status}")
        
        except aiohttp.ClientError as e:
            validation_result['errors'].append(f'Network error during validation: {str(e)}')
            logger.error(f"NASA token validation network error: {e}")
        except Exception as e:
            validation_result['errors'].append(f'Validation error: {str(e)}')
            logger.error(f"NASA token validation failed: {e}")
        
        return validation_result
    
    async def test_api_access(self) -> Dict[str, Any]:
        """Test access to NASA APIs with current token"""
        test_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'services': {},
            'overall_status': 'unknown'
        }
        
        if not self.earthdata_token:
            test_results['overall_status'] = 'no_token'
            return test_results
        
        headers = self.get_auth_headers()
        
        # Test CMR access
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.cmr_base_url}/search/collections.json"
                params = {"page_size": 1}
                
                async with session.get(url, headers=headers, params=params, timeout=15) as response:
                    test_results['services']['cmr'] = {
                        'status': 'accessible' if response.status == 200 else 'error',
                        'response_code': response.status,
                        'endpoint': 'collections search'
                    }
        except Exception as e:
            test_results['services']['cmr'] = {
                'status': 'error',
                'error': str(e),
                'endpoint': 'collections search'
            }
        
        # Test GIBS access (GIBS is public, no auth needed but test availability)
        try:
            async with aiohttp.ClientSession() as session:
                # Test GIBS capabilities endpoint
                url = f"{self.gibs_base_url}/wmts/epsg4326/best/wmts.cgi"
                params = {"SERVICE": "WMTS", "VERSION": "1.0.0", "REQUEST": "GetCapabilities"}
                
                async with session.get(url, params=params, timeout=15) as response:
                    test_results['services']['gibs'] = {
                        'status': 'accessible' if response.status == 200 else 'error',
                        'response_code': response.status,
                        'endpoint': 'capabilities'
                    }
        except Exception as e:
            test_results['services']['gibs'] = {
                'status': 'error',
                'error': str(e),
                'endpoint': 'capabilities'
            }
        
        # Determine overall status
        service_statuses = [service.get('status') for service in test_results['services'].values()]
        if all(status == 'accessible' for status in service_statuses):
            test_results['overall_status'] = 'all_accessible'
        elif any(status == 'accessible' for status in service_statuses):
            test_results['overall_status'] = 'partial_access'
        else:
            test_results['overall_status'] = 'no_access'
        
        return test_results
    
    def get_token_info(self) -> Dict[str, Any]:
        """Get token information for admin dashboard"""
        info = {
            'configured': bool(self.earthdata_token),
            'metadata': self.token_metadata,
            'security_status': 'secure' if self.earthdata_token else 'not_configured'
        }
        
        if self.token_metadata:
            now = datetime.now(timezone.utc)
            expires_at = self.token_metadata['expires_at']
            
            info.update({
                'days_until_expiry': (expires_at - now).days,
                'expires_at': expires_at.isoformat(),
                'user_id': self.token_metadata.get('user_id'),
                'issuer': self.token_metadata.get('issuer')
            })
            
            # Security warnings
            if (expires_at - now).days <= 7:
                info['warnings'] = ['Token expires within 7 days']
            elif (expires_at - now).days <= 30:
                info['warnings'] = ['Token expires within 30 days']
        
        return info
    
    def log_api_usage(self, service: str, endpoint: str, status_code: int, 
                     response_size: Optional[int] = None, duration_ms: Optional[float] = None):
        """Log NASA API usage for monitoring and compliance"""
        usage_log = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'service': service,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_size_bytes': response_size,
            'duration_ms': duration_ms,
            'user_id': self.token_metadata.get('user_id') if self.token_metadata else None,
            'token_configured': bool(self.earthdata_token)
        }
        
        # Log to application logger
        logger.info(f"NASA API Usage: {service} {endpoint} -> {status_code} "
                   f"({response_size}B, {duration_ms}ms)")
        
        # Store usage data for admin reporting (cache with 24h TTL)
        cache_key = f"nasa_usage:{datetime.now().strftime('%Y%m%d')}"
        
        try:
            # Get today's usage log
            today_usage = cache_service.redis_client.get(cache_key) if cache_service.redis_client else None
            usage_list = json.loads(today_usage) if today_usage else []
            
            # Add new usage entry
            usage_list.append(usage_log)
            
            # Keep only last 1000 entries per day
            if len(usage_list) > 1000:
                usage_list = usage_list[-1000:]
            
            # Store back to cache
            if cache_service.redis_client:
                cache_service.redis_client.setex(cache_key, 86400, json.dumps(usage_list))  # 24h TTL
        
        except Exception as e:
            logger.warning(f"Failed to store NASA usage log: {e}")
    
    async def get_usage_statistics(self, days_back: int = 7) -> Dict[str, Any]:
        """Get NASA API usage statistics for admin dashboard"""
        try:
            usage_stats = {
                'period_days': days_back,
                'daily_stats': {},
                'service_breakdown': {},
                'status_code_breakdown': {},
                'total_requests': 0,
                'average_response_time_ms': 0
            }
            
            total_duration = 0
            total_requests = 0
            
            # Collect usage data for the specified period
            for i in range(days_back):
                date = datetime.now() - timedelta(days=i)
                cache_key = f"nasa_usage:{date.strftime('%Y%m%d')}"
                
                try:
                    daily_data = cache_service.redis_client.get(cache_key) if cache_service.redis_client else None
                    if daily_data:
                        usage_list = json.loads(daily_data)
                        
                        daily_requests = len(usage_list)
                        daily_services = {}
                        daily_status_codes = {}
                        daily_total_duration = 0
                        
                        for entry in usage_list:
                            # Service breakdown
                            service = entry.get('service', 'unknown')
                            daily_services[service] = daily_services.get(service, 0) + 1
                            
                            # Status code breakdown
                            status = entry.get('status_code', 0)
                            daily_status_codes[status] = daily_status_codes.get(status, 0) + 1
                            
                            # Duration tracking
                            if entry.get('duration_ms'):
                                daily_total_duration += entry['duration_ms']
                        
                        usage_stats['daily_stats'][date.strftime('%Y-%m-%d')] = {
                            'requests': daily_requests,
                            'services': daily_services,
                            'status_codes': daily_status_codes,
                            'avg_response_time_ms': daily_total_duration / daily_requests if daily_requests > 0 else 0
                        }
                        
                        # Aggregate totals
                        total_requests += daily_requests
                        total_duration += daily_total_duration
                        
                        # Aggregate service breakdown
                        for service, count in daily_services.items():
                            usage_stats['service_breakdown'][service] = usage_stats['service_breakdown'].get(service, 0) + count
                        
                        # Aggregate status codes
                        for status, count in daily_status_codes.items():
                            usage_stats['status_code_breakdown'][status] = usage_stats['status_code_breakdown'].get(status, 0) + count
                
                except Exception as e:
                    logger.warning(f"Failed to load usage data for {date.strftime('%Y-%m-%d')}: {e}")
            
            usage_stats['total_requests'] = total_requests
            usage_stats['average_response_time_ms'] = total_duration / total_requests if total_requests > 0 else 0
            
            # Calculate success rate
            success_codes = [200, 201, 202, 204]
            successful_requests = sum(usage_stats['status_code_breakdown'].get(code, 0) for code in success_codes)
            usage_stats['success_rate'] = successful_requests / total_requests if total_requests > 0 else 0
            
            return usage_stats
            
        except Exception as e:
            logger.error(f"Failed to generate usage statistics: {e}")
            return {'error': str(e)}
    
    def is_token_valid(self) -> bool:
        """Check if token is configured and not expired"""
        if not self.earthdata_token or not self.token_metadata:
            return False
        
        now = datetime.now(timezone.utc)
        expires_at = self.token_metadata['expires_at']
        
        return now < expires_at
    
    def get_token_expiry_warning(self) -> Optional[str]:
        """Get warning message if token is expiring soon"""
        if not self.token_metadata:
            return None
        
        now = datetime.now(timezone.utc)
        expires_at = self.token_metadata['expires_at']
        days_remaining = (expires_at - now).days
        
        if days_remaining <= 0:
            return "NASA token has expired and needs immediate renewal"
        elif days_remaining <= 7:
            return f"NASA token expires in {days_remaining} days - renewal recommended"
        elif days_remaining <= 30:
            return f"NASA token expires in {days_remaining} days"
        
        return None
    
    async def refresh_token_if_needed(self) -> Dict[str, Any]:
        """Attempt to refresh token using username/password if available"""
        refresh_result = {
            'refreshed': False,
            'new_token_set': False,
            'message': '',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if not self.earthdata_username or not self.earthdata_password:
            refresh_result['message'] = 'Username/password not configured for token refresh'
            return refresh_result
        
        try:
            # NASA Earthdata token refresh endpoint
            auth_data = {
                'username': self.earthdata_username,
                'password': self.earthdata_password
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.urs_base_url}/api/users/tokens"
                async with session.post(url, json=auth_data, timeout=30) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        new_token = token_data.get('access_token')
                        
                        if new_token:
                            # Note: In production, you'd update environment variable
                            # This is a demo of the refresh process
                            refresh_result.update({
                                'refreshed': True,
                                'message': 'Token refresh successful (update NASA_EARTHDATA_TOKEN environment variable)',
                                'token_preview': f"{new_token[:20]}...{new_token[-10:]}",
                                'expires_in_days': 60  # NASA tokens typically expire in 60 days
                            })
                            
                            logger.info("NASA token refreshed successfully")
                        else:
                            refresh_result['message'] = 'Token refresh response missing access_token'
                    else:
                        refresh_result['message'] = f'Token refresh failed with status {response.status}'
                        
        except Exception as e:
            refresh_result['message'] = f'Token refresh error: {str(e)}'
            logger.error(f"NASA token refresh failed: {e}")
        
        return refresh_result

# Singleton instance for global use
nasa_auth_service = NASAAuthService()
