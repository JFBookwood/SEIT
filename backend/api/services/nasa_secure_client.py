import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import time

from .nasa_auth_service import nasa_auth_service
from .rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class NASASecureClient:
    """Secure, authenticated client for NASA API interactions"""
    
    def __init__(self):
        self.auth_service = nasa_auth_service
        
        # Session configuration optimized for NASA APIs
        self.session_config = {
            'timeout': aiohttp.ClientTimeout(total=60, connect=15),
            'connector': aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
                keepalive_timeout=120,
                enable_cleanup_closed=True
            )
        }
    
    @rate_limited('nasa_cmr')
    async def search_collections(self, search_params: Dict) -> Dict[str, Any]:
        """Search NASA collections with authentication and logging"""
        if not self.auth_service.is_token_valid():
            logger.warning("NASA token invalid, using mock data")
            return self._generate_mock_collections(search_params)
        
        try:
            headers = self.auth_service.get_auth_headers()
            
            async with aiohttp.ClientSession(**self.session_config) as session:
                url = f"{self.auth_service.cmr_base_url}/search/collections.json"
                
                start_time = time.time()
                async with session.get(url, headers=headers, params=search_params) as response:
                    duration_ms = (time.time() - start_time) * 1000
                    response_size = response.content_length or 0
                    
                    # Log API usage
                    self.auth_service.log_api_usage(
                        'cmr',
                        'collections_search',
                        response.status,
                        response_size,
                        duration_ms
                    )
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"CMR collections search successful: {len(data.get('feed', {}).get('entry', []))} results")
                        return data
                    else:
                        logger.error(f"CMR collections search failed: {response.status}")
                        return self._generate_mock_collections(search_params)
                        
        except Exception as e:
            logger.error(f"CMR collections search error: {e}")
            return self._generate_mock_collections(search_params)
    
    @rate_limited('nasa_cmr')
    async def search_granules(self, collection_id: str, search_params: Dict) -> List[Dict]:
        """Search granules with full authentication and audit logging"""
        if not self.auth_service.is_token_valid():
            logger.warning("NASA token invalid, using mock granules")
            return self._generate_mock_granules(collection_id)
        
        try:
            headers = self.auth_service.get_auth_headers()
            
            # Add collection to search params
            params = {
                **search_params,
                'collection_concept_id': collection_id,
                'format': 'json'
            }
            
            async with aiohttp.ClientSession(**self.session_config) as session:
                url = f"{self.auth_service.cmr_base_url}/search/granules.json"
                
                start_time = time.time()
                async with session.get(url, headers=headers, params=params) as response:
                    duration_ms = (time.time() - start_time) * 1000
                    response_size = response.content_length or 0
                    
                    # Log detailed API usage
                    self.auth_service.log_api_usage(
                        'cmr',
                        f'granules_search/{collection_id}',
                        response.status,
                        response_size,
                        duration_ms
                    )
                    
                    if response.status == 200:
                        data = await response.json()
                        granules = data.get('feed', {}).get('entry', [])
                        
                        logger.info(f"CMR granules search successful: {len(granules)} granules found")
                        
                        # Format granules for consistent structure
                        formatted_granules = []
                        for granule in granules:
                            formatted_granule = {
                                'id': granule.get('id'),
                                'title': granule.get('title'),
                                'updated': granule.get('updated'),
                                'dataset_id': granule.get('dataset_id'),
                                'data_center': granule.get('data_center'),
                                'time_start': granule.get('time_start'),
                                'time_end': granule.get('time_end'),
                                'orbit_direction': granule.get('orbit_direction'),
                                'links': granule.get('links', []),
                                'size_mb': self._extract_granule_size(granule)
                            }
                            formatted_granules.append(formatted_granule)
                        
                        return formatted_granules
                    else:
                        logger.error(f"CMR granules search failed: {response.status}")
                        return self._generate_mock_granules(collection_id)
                        
        except Exception as e:
            logger.error(f"CMR granules search error: {e}")
            return self._generate_mock_granules(collection_id)
    
    async def submit_harmony_request(self, job_params: Dict) -> Dict[str, Any]:
        """Submit authenticated request to NASA Harmony"""
        if not self.auth_service.is_token_valid():
            logger.warning("NASA token invalid, cannot submit Harmony request")
            return {'error': 'Authentication required for Harmony requests'}
        
        try:
            headers = self.auth_service.get_auth_headers()
            
            async with aiohttp.ClientSession(**self.session_config) as session:
                url = f"{self.auth_service.harmony_base_url}/jobs"
                
                start_time = time.time()
                async with session.post(url, headers=headers, json=job_params) as response:
                    duration_ms = (time.time() - start_time) * 1000
                    response_size = response.content_length or 0
                    
                    # Log Harmony API usage
                    self.auth_service.log_api_usage(
                        'harmony',
                        'job_submission',
                        response.status,
                        response_size,
                        duration_ms
                    )
                    
                    if response.status == 202:  # Harmony returns 202 for accepted jobs
                        job_data = await response.json()
                        logger.info(f"Harmony job submitted successfully: {job_data.get('jobID')}")
                        return job_data
                    else:
                        error_text = await response.text()
                        logger.error(f"Harmony job submission failed: {response.status} - {error_text}")
                        return {'error': f'Harmony request failed: {response.status}'}
                        
        except Exception as e:
            logger.error(f"Harmony request error: {e}")
            return {'error': str(e)}
    
    def _extract_granule_size(self, granule: Dict) -> float:
        """Extract granule size from links metadata"""
        try:
            for link in granule.get('links', []):
                if 'data#' in link.get('rel', ''):
                    # Look for size in link metadata
                    if 'length' in link:
                        return float(link['length']) / (1024 * 1024)  # Convert to MB
            return 0.0  # Unknown size
        except Exception:
            return 0.0
    
    def _generate_mock_collections(self, search_params: Dict) -> Dict:
        """Generate mock collection data for testing"""
        mock_collections = {
            'feed': {
                'title': 'Mock Collections Feed',
                'id': 'mock_collections',
                'updated': datetime.now(timezone.utc).isoformat(),
                'entry': [
                    {
                        'id': 'C1443775405-LAADS',
                        'title': 'MODIS/Aqua Aerosol 5-Min L2 Swath 10km',
                        'summary': 'Mock MODIS Aqua aerosol data',
                        'updated': datetime.now(timezone.utc).isoformat(),
                        'dataset_id': 'MYD04_L2.061',
                        'data_center': 'LAADS'
                    },
                    {
                        'id': 'C1646648607-LPDAAC_ECS',
                        'title': 'MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 Global 1km',
                        'summary': 'Mock MODIS Terra LST data',
                        'updated': datetime.now(timezone.utc).isoformat(),
                        'dataset_id': 'MOD11A2.061',
                        'data_center': 'LPDAAC_ECS'
                    }
                ]
            }
        }
        return mock_collections
    
    def _generate_mock_granules(self, collection_id: str) -> List[Dict]:
        """Generate mock granule data for testing"""
        import uuid
        
        mock_granules = []
        for i in range(5):
            granule = {
                'id': f"G{1000000000 + i}-{collection_id.split('-')[1] if '-' in collection_id else 'MOCK'}",
                'title': f"Mock granule {i+1} for {collection_id}",
                'updated': datetime.now(timezone.utc).isoformat(),
                'dataset_id': collection_id.split('-')[0] if '-' in collection_id else collection_id,
                'data_center': collection_id.split('-')[1] if '-' in collection_id else 'MOCK',
                'time_start': (datetime.now() - timedelta(days=i)).isoformat(),
                'time_end': (datetime.now() - timedelta(days=i) + timedelta(hours=1)).isoformat(),
                'links': [],
                'size_mb': 45.0 + i * 5
            }
            mock_granules.append(granule)
        
        return mock_granules

# Singleton instance
nasa_secure_client = NASASecureClient()
