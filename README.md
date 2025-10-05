# 🌍 SEIT - Space Environmental Impact Tracker
A[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![React](https://img.shields.io/badge/React-18.2.0-blue.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.103.0-green.svg)](https://fastapi.tiangolo.com/)
[![NASA GIBS](https://img.shields.io/badge/NASA-GIBS-red.svg)](https://gibs.earthdata.nasa.gov/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

> **A production-ready environmental monitoring platform integrating NASA satellite data, real-time sensor networks, and advanced air quality analytics.**

SEIT provides real-time air quality monitoring through an interactive web platform that combines satellite imagery from NASA GIBS, sensor data from PurpleAir and Sensor.Community networks, and sophisticated analytics for pollution hotspot detection and anomaly analysis.

## 🚀 Live Demo

- **Demo**: [https://seit.biela.dev](https://seit.biela.dev)
- **API Docs**: [https://seit.biela.dev/docs](https://seit.biela.dev/docs)

![SEIT Dashboard Screenshot](https://images.unsplash.com/photo-1611273426858-450d8e3c9fce?w=800&h=400&fit=crop)

## ✨ Key Features
## Features

### 🌍 Interactive Mapping
- **NASA GIBS Integration**: Real-time satellite imagery and environmental data layers
- **Multi-source Sensors**: PurpleAir, Sensor.Community, and custom uploaded data
- **Time Animation**: Date picker with playback controls for temporal analysis
- **Layer Management**: Toggle between satellite layers and sensor data overlays

### 📊 Advanced Analytics
- **Hotspot Detection**: DBSCAN clustering algorithm for pollution hotspot identification
- **Anomaly Detection**: Machine learning models (Isolation Forest, Autoencoders) for unusual pattern detection
- **Trend Analysis**: Statistical analysis of temporal environmental trends
- **Real-time Processing**: Background job processing with Celery/Redis

### 🛰️ Satellite Data Integration
- **NASA GIBS WMTS**: Direct integration with NASA's Global Imagery Browse Services
- **Harmony API**: Automated data subsetting and processing through NASA Harmony
- **Product Catalog**: Support for MODIS, AIRS, and other Earth observation missions
- **Automated Caching**: Intelligent caching system for satellite data products

### 📱 Modern UI/UX
- **Dark Mode Support**: Full dark/light theme toggle
- **Responsive Design**: Mobile-first approach with perfect cross-device compatibility
- **Interactive Dashboard**: Real-time statistics and system monitoring
- **Detail Panels**: Comprehensive sensor data visualization with time series charts

## Quick Start

### Prerequisites

1. **NASA Earthdata Account** (Required for satellite data)
   - Register at [https://urs.earthdata.nasa.gov/](https://urs.earthdata.nasa.gov/)
   - Accept EULA for data access
   - Note: Some satellite products may require additional DAAC-specific approvals

2. **PurpleAir API Key** (Optional for live sensor data)
   - Register at [https://www2.purpleair.com/](https://www2.purpleair.com/)
   - Generate API key in dashboard

3. **Docker & Docker Compose**
   - Install from [https://docker.com/](https://docker.com/)

### Environment Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd seit
```

2. **Configure environment variables**
```bash
cp backend/.env.example .env
```

Edit `.env` with your API credentials:
```env
# NASA Earthdata (Required)
EARTHDATA_USERNAME=your_earthdata_username
EARTHDATA_PASSWORD=your_earthdata_password

# PurpleAir (Optional)
PURPLEAIR_API_KEY=your_purpleair_key

# Security
SECRET_KEY=generate-a-secure-random-key

# Database
DATABASE_URL=sqlite:///./data/seit.db
```

3. **Launch with Docker Compose**
```bash
docker-compose up --build
```

The application will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Development Setup

### Frontend Development
```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev
```

### Backend Development
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
python main.py
```

## API Endpoints

### Satellite Data
- `GET /api/satellite/gibs/layers` - Available GIBS layers
- `GET /api/satellite/gibs/tile-url` - Generate tile URLs
- `POST /api/satellite/products/query` - Query satellite granules
- `POST /api/satellite/products/subset` - Request data subsets

### Sensor Data
- `GET /api/sensors/purpleair/sensors` - PurpleAir sensor network
- `GET /api/sensors/sensor-community/sensors` - Sensor.Community data
- `POST /api/sensors/upload` - Upload custom sensor data
- `POST /api/sensors/sync/purpleair` - Sync PurpleAir data to database

### Analytics
- `POST /api/analytics/hotspots` - Detect pollution hotspots
- `POST /api/analytics/anomalies` - Run anomaly detection
- `GET /api/analytics/trends` - Analyze temporal trends
- `GET /api/analytics/summary` - Generate analytics summary

### Data Export
- `GET /api/export/sensor-data/csv` - Export sensor data as CSV
- `GET /api/export/sensor-data/geojson` - Export as GeoJSON
- `GET /api/export/report/pdf` - Generate comprehensive PDF reports

## Architecture

### Frontend Stack
- **React 18** - Modern React with hooks
- **Vite** - Fast build tool and dev server  
- **Leaflet/MapboxGL** - Interactive mapping components
- **Tailwind CSS + Relume** - Responsive styling framework
- **Recharts** - Data visualization and charting
- **Zustand** - Lightweight state management

### Backend Stack
- **FastAPI** - High-performance Python web framework
- **SQLAlchemy** - Database ORM with Alembic migrations
- **Pandas + NumPy** - Data processing and analysis
- **Scikit-learn** - Machine learning algorithms
- **XArray + Rasterio** - Geospatial data processing
- **Celery + Redis** - Background job processing

### External Integrations
- **NASA GIBS WMTS** - Satellite imagery tiles
- **NASA Harmony** - Data subsetting and processing
- **NASA CMR** - Metadata and granule search
- **PurpleAir API** - Real-time air quality sensors
- **Sensor.Community API** - Open sensor network data

## Data Processing Pipeline

### 1. Satellite Data Workflow
```
CMR Search → Harmony Subset Request → Background Processing → Cache Storage → Frontend Display
```

### 2. Sensor Data Workflow  
```
API Ingestion → Data Normalization → Database Storage → Real-time Analytics → Map Visualization
```

### 3. Analytics Pipeline
```
Data Aggregation → Spatial Gridding → ML Processing → Results Caching → Export Generation
```

## Deployment Options

### Docker (Recommended)
```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud Platforms

#### Render.com
1. Fork this repository
2. Create new Web Service on Render
3. Connect your GitHub repository
4. Set environment variables in Render dashboard
5. Deploy with automatic HTTPS

#### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway link
railway up
```

#### AWS/GCP/Azure
Use provided Dockerfiles with your preferred container orchestration platform (ECS, Cloud Run, Container Instances).

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `EARTHDATA_USERNAME` | Yes | NASA Earthdata login username |
| `EARTHDATA_PASSWORD` | Yes | NASA Earthdata login password |
| `PURPLEAIR_API_KEY` | No | PurpleAir API key for live sensor data |
| `OPENWEATHER_API_KEY` | No | OpenWeatherMap API key for weather overlays |
| `SECRET_KEY` | Yes | JWT secret key for authentication |
| `DATABASE_URL` | No | Database connection string (default: SQLite) |
| `REDIS_URL` | No | Redis connection for job queueing |
| `CACHE_DIR` | No | File system cache directory |

### NASA Earthdata Requirements

**Important EULA Notes:**
- NASA Earthdata requires acceptance of End User License Agreements
- Some datasets may have usage restrictions or require additional approvals
- Review data usage policies at [https://earthdata.nasa.gov/](https://earthdata.nasa.gov/)
- Comply with NASA's data citation requirements in any published research

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Tests  
```bash
pnpm test
```

### API Testing
Import the provided Postman collection or use the cURL examples:

```bash
# Health check
curl http://localhost:8000/api/health

# Get GIBS layers
curl http://localhost:8000/api/satellite/gibs/layers

# Query sensor data
curl "http://localhost:8000/api/sensors/data?bbox=-122.5,37.3,-122.0,37.8"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **NASA GIBS** - Global Imagery Browse Services for satellite data
- **NASA Harmony** - Data transformation and subsetting services  
- **PurpleAir** - Real-time air quality sensor network
- **Sensor.Community** - Open environmental sensor data
- **OpenStreetMap** - Base map tile services

## Support

For questions, issues, or contributions:
- 📧 Email: support@biela.dev
- 🐛 Issues: GitHub Issues tracker
- 📚 Documentation: [Project Wiki](link-to-wiki)
- �� Discord: [Community Server](link-to-discord)

---

**Production Ready Features:**
✅ Docker containerization  
✅ Environment-based configuration  
✅ Health checks and monitoring  
✅ Comprehensive error handling  
✅ API documentation with OpenAPI  
✅ Responsive web design  
✅ Dark mode support  
✅ Data export capabilities  
✅ Background job processing  
✅ Caching layer implementation  
✅ Security best practices  
✅ Unit test coverage  
