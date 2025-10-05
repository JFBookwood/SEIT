from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv
import uvicorn
from contextlib import asynccontextmanager

from api.routes import satellite, sensors, analytics, admin, export
from api.routes import health
from api.routes.enhanced_sensors import router as enhanced_sensors_router
from api.routes.async_integration import router as async_integration_router
from api.routes.harmonized_data import router as harmonized_data_router
from api.routes.calibration import router as calibration_router
from api.routes.heatmap import router as heatmap_router
from api.database import engine, Base
from api.auth import get_current_user
from api.models import User
from api.middleware.nasa_security_middleware import NASASecurityMiddleware

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="SEIT - Space Environmental Impact Tracker",
    description="Production-ready environmental monitoring with satellite data integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add NASA security middleware
app.middleware("http")(NASASecurityMiddleware())
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://localhost:4173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173", 
        "http://127.0.0.1:4173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(satellite.router, prefix="/api/satellite", tags=["satellite"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(enhanced_sensors_router, prefix="/api/sensors", tags=["enhanced-sensors"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(async_integration_router, prefix="/api/sensors", tags=["async-integration"])
app.include_router(harmonized_data_router, prefix="/api/sensors", tags=["harmonized-data"])
app.include_router(calibration_router, prefix="/api", tags=["calibration"])
app.include_router(heatmap_router, prefix="/api", tags=["heatmap"])

@app.get("/")
async def root():
    return {
        "message": "SEIT - Space Environmental Impact Tracker API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "SEIT Backend"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )
