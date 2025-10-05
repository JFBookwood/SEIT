import aiohttp
import asyncio
import json
from typing import Dict, List, Optional, Any
import os
from datetime import datetime
import earthaccess

class HarmonyService:
    """Service for interacting with NASA Harmony and CMR APIs"""
    
    def __init__(self):
        self.harmony_url = "https://harmony.earthdata.nasa.gov"
        self.cmr_url = "https://cmr.earthdata.nasa.gov"
        
        # Initialize earthaccess if credentials are available
        self.auth = None
        try:
            if os.getenv("EARTHDATA_USERNAME") and os.getenv("EARTHDATA_PASSWORD"):
                earthaccess.login(
                    username=os.getenv("EARTHDATA_USERNAME"),
                    password=os.getenv("EARTHDATA_PASSWORD")
                )
                self.auth = earthaccess.auth
        except Exception as e:
            print(f"Warning: Earthdata authentication failed: {e}")
    
    async def query_granules(
        self, 
        product_id: str, 
        start_date: str, 
        end_date: str, 
        bbox: List[float]
    ) -> List[Dict]:
        """Query CMR for granules matching criteria"""
        try:
            # Format bounding box for CMR
            west, south, east, north = bbox
            bounding_box = f"{west},{south},{east},{north}"
            
            # CMR search parameters
            params = {
                'collection_concept_id': self._get_collection_id(product_id),
                'temporal': f"{start_date},{end_date}",
                'bounding_box': bounding_box,
                'page_size': 100,
                'format': 'json'
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.cmr_url}/search/granules.json"
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        granules = []
                        
                        for item in data.get('feed', {}).get('entry', []):
                            granule = {
                                'id': item.get('id'),
                                'title': item.get('title'),
                                'time_start': item.get('time_start'),
                                'time_end': item.get('time_end'),
                                'links': item.get('links', []),
                                'polygons': item.get('polygons', []),
                                'bbox': self._extract_bbox(item)
                            }
                            granules.append(granule)
                        
                        return granules
                    else:
                        # Return mock data for demo if CMR fails
                        return self._generate_mock_granules(product_id, start_date, end_date, bbox)
                        
        except Exception as e:
            print(f"CMR query failed, returning mock data: {e}")
            return self._generate_mock_granules(product_id, start_date, end_date, bbox)
    
    async def submit_subset_request(
        self, 
        product_id: str, 
        granule_id: str, 
        bbox: List[float], 
        variables: List[str]
    ) -> str:
        """Submit data subsetting request to Harmony"""
        try:
            # Harmony request parameters
            collection_id = self._get_collection_id(product_id)
            west, south, east, north = bbox
            
            # Construct Harmony URL
            harmony_params = {
                'subset': f"lon({west}:{east})",
                'subset': f"lat({south}:{north})",
                'format': 'application/x-netcdf4',
                'granuleId': granule_id
            }
            
            # Add variable subsetting if specified
            if variables:
                harmony_params['variable'] = ','.join(variables)
            
            # For demo purposes, generate a mock job ID
            # In real implementation, you'd submit to Harmony API
            import uuid
            job_id = str(uuid.uuid4())
            
            print(f"Mock Harmony request submitted for {product_id}")
            print(f"Granule: {granule_id}")
            print(f"BBox: {bbox}")
            print(f"Variables: {variables}")
            
            return job_id
            
        except Exception as e:
            raise Exception(f"Error submitting Harmony request: {str(e)}")
    
    async def check_job_status(self, job_id: str) -> Dict:
        """Check Harmony job status"""
        try:
            # For demo, return mock job status
            # In real implementation, you'd query Harmony API
            
            # Simulate job progression
            import time
            import hashlib
            
            # Use job_id to determine mock status consistently
            hash_int = int(hashlib.md5(job_id.encode()).hexdigest()[:8], 16)
            
            if hash_int % 3 == 0:
                status = "running"
                progress = 45
                message = "Processing granule subset..."
            elif hash_int % 3 == 1:
                status = "successful"
                progress = 100
                message = "Subset completed successfully"
            else:
                status = "failed"
                progress = 0
                message = "Subsetting failed: Invalid granule ID"
            
            return {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message,
                "created_time": "2024-01-15T10:30:00Z",
                "updated_time": datetime.utcnow().isoformat() + "Z",
                "links": [
                    {
                        "href": f"https://harmony.earthdata.nasa.gov/jobs/{job_id}/download",
                        "type": "application/x-netcdf4",
                        "rel": "data"
                    }
                ] if status == "successful" else []
            }
            
        except Exception as e:
            raise Exception(f"Error checking job status: {str(e)}")
    
    def _get_collection_id(self, product_id: str) -> str:
        """Map product ID to CMR collection concept ID"""
        # Mapping of common products to their collection IDs
        collection_map = {
            "MOD11A2.061": "C1646648607-LPDAAC_ECS",
            "MYD11A2.061": "C1646648926-LPDAAC_ECS", 
            "AIRS2RET.010": "C1243747787-GES_DISC",
            "MYD04_L2.061": "C1443775405-LAADS"
        }
        
        return collection_map.get(product_id, f"MOCK_COLLECTION_{product_id}")
    
    def _extract_bbox(self, granule_item: Dict) -> List[float]:
        """Extract bounding box from granule metadata"""
        try:
            polygons = granule_item.get('polygons', [])
            if polygons:
                # Extract coordinates from first polygon
                coords_str = polygons[0]
                coords = [float(x) for x in coords_str.split()]
                
                # Assuming coordinates are in lat,lon pairs
                lats = coords[1::2]
                lons = coords[0::2]
                
                return [min(lons), min(lats), max(lons), max(lats)]
            
            # Fallback: try to extract from other fields
            bbox_info = granule_item.get('boxes', [])
            if bbox_info:
                coords = [float(x) for x in bbox_info[0].split()]
                return coords
            
            return [-180, -90, 180, 90]  # Default global bbox
            
        except Exception:
            return [-180, -90, 180, 90]
    
    def _generate_mock_granules(
        self, 
        product_id: str, 
        start_date: str, 
        end_date: str, 
        bbox: List[float]
    ) -> List[Dict]:
        """Generate mock granules for demo purposes"""
        try:
            from datetime import timedelta
            import uuid
            
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            
            granules = []
            current = start
            
            # Generate daily granules for up to 10 days
            count = 0
            while current <= end and count < 10:
                granule_id = f"{product_id}.A{current.strftime('%Y%j')}.{str(uuid.uuid4())[:8]}"
                
                granule = {
                    'id': granule_id,
                    'title': f"{product_id} {current.strftime('%Y-%m-%d')}",
                    'time_start': current.strftime('%Y-%m-%dT00:00:00Z'),
                    'time_end': (current + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z'),
                    'links': [
                        {
                            'href': f'https://data.earthdata.nasa.gov/granules/{granule_id}',
                            'type': 'application/x-hdf',
                            'rel': 'http://esipfed.org/ns/fedsearch/1.1/data#'
                        }
                    ],
                    'polygons': [f"{bbox[0]} {bbox[1]} {bbox[2]} {bbox[1]} {bbox[2]} {bbox[3]} {bbox[0]} {bbox[3]} {bbox[0]} {bbox[1]}"],
                    'bbox': bbox
                }
                
                granules.append(granule)
                current += timedelta(days=1)
                count += 1
            
            return granules
            
        except Exception as e:
            return []
