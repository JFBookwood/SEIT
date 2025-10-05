import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import time

logger = logging.getLogger(__name__)

class NASASecurityMiddleware:
    """Security middleware for NASA-related endpoints"""
    
    def __init__(self):
        # Track requests that involve NASA data
        self.nasa_endpoints = [
            '/api/satellite/',
            '/api/admin/nasa/',
            '/api/sensors/enhanced-integration'
        ]
        
        # Security headers for NASA compliance
        self.nasa_security_headers = {
            'X-NASA-Data-Usage': 'Compliant-Educational-Research',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
    
    async def __call__(self, request: Request, call_next):
        """Process request with NASA security considerations"""
        start_time = time.time()
        
        # Check if this is a NASA-related request
        is_nasa_request = any(request.url.path.startswith(endpoint) for endpoint in self.nasa_endpoints)
        
        if is_nasa_request:
            # Log NASA data access
            logger.info(f"NASA data access: {request.method} {request.url.path} from {request.client.host}")
            
            # Add security context to request
            request.state.nasa_data_access = True
            request.state.access_timestamp = datetime.now()
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Add NASA compliance headers for relevant endpoints
            if is_nasa_request:
                for header, value in self.nasa_security_headers.items():
                    response.headers[header] = value
                
                # Add processing time header
                processing_time = (time.time() - start_time) * 1000
                response.headers['X-Processing-Time-Ms'] = str(round(processing_time, 2))
                
                # Log successful NASA data delivery
                logger.info(f"NASA data delivered: {request.url.path} -> {response.status_code} ({processing_time:.1f}ms)")
            
            return response
            
        except Exception as e:
            # Log NASA-related errors with higher priority
            if is_nasa_request:
                logger.error(f"NASA endpoint error: {request.url.path} -> {str(e)}")
            
            # Return appropriate error response
            return JSONResponse(
                status_code=500,
                content={'error': 'Internal server error', 'nasa_endpoint': is_nasa_request},
                headers=self.nasa_security_headers if is_nasa_request else {}
            )
