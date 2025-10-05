# 🚀 SEIT Deployment Guide

## 📋 Deployment Options

### 1. Docker Compose (Recommended)

#### Production Deployment
```bash
# Clone repository
git clone https://github.com/yourusername/seit.git
cd seit

# Configure environment
cp backend/.env.example .env
# Edit .env with your API keys and settings

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

#### Services
- **Frontend**: Nginx serving React build on port 3000
- **Backend**: FastAPI application on port 8000
- **Database**: PostgreSQL with persistent volumes
- **Cache**: Redis for session management and job queues

### 2. Cloud Platform Deployment

#### Render.com
1. Fork this repository to your GitHub account
2. Create new Web Service on Render
3. Connect your GitHub repository
4. Configure environment variables in Render dashboard
5. Deploy with automatic HTTPS and custom domain

#### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway link
railway up
```

#### Vercel (Frontend Only)
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy frontend
vercel --prod
```

#### AWS/GCP/Azure
Use provided Dockerfiles with your preferred container service:
- **AWS**: ECS with Fargate
- **GCP**: Cloud Run
- **Azure**: Container Instances

### 3. Traditional VPS/Server

#### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: 2 cores minimum, 4 cores recommended
- **Storage**: 20GB minimum, 50GB recommended
- **Network**: Stable internet connection for API access

#### Installation Steps
```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone and configure
git clone https://github.com/yourusername/seit.git
cd seit
cp backend/.env.example .env

# 5. Configure environment variables
nano .env

# 6. Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## 🔧 Environment Configuration

### Required Variables
```env
# Database (Production)
DATABASE_URL=postgresql://user:password@localhost:5432/seit

# Security (REQUIRED - Generate strong values)
SECRET_KEY=your-super-secret-jwt-key-here

# NASA Earthdata (REQUIRED for satellite data)
NASA_EARTHDATA_TOKEN=your-nasa-earthdata-token
EARTHDATA_USERNAME=your-earthdata-username
EARTHDATA_PASSWORD=your-earthdata-password

# External APIs (Optional - app works with mock data)
PURPLEAIR_API_KEY=your-purpleair-api-key
OPENWEATHER_API_KEY=your-openweather-api-key
```

### Optional Variables
```env
# Redis (for job queues)
REDIS_URL=redis://localhost:6379/0

# File Storage
CACHE_DIR=/app/cache
LOG_FILE=/app/logs/application.log

# Application Settings
ENVIRONMENT=production
PORT=8000
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## �� Security Setup

### 1. NASA Earthdata Account
1. Register at [https://urs.earthdata.nasa.gov/](https://urs.earthdata.nasa.gov/)
2. Accept required EULAs for data access
3. Generate application token
4. Store token as `NASA_EARTHDATA_TOKEN` environment variable

### 2. SSL/HTTPS Configuration
```nginx
# nginx.conf for SSL termination
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Firewall Configuration
```bash
# UFW firewall setup
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

## 📊 Monitoring & Health Checks

### Health Check Endpoints
- **Backend Health**: `GET /api/health`
- **System Status**: `GET /api/admin/status`
- **NASA Token**: `GET /api/admin/nasa/validate-token`

### Monitoring Setup
```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### Log Management
```bash
# View application logs
docker-compose logs -f backend

# View all service logs
docker-compose logs -f

# Log rotation setup
echo "/var/log/seit/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}" | sudo tee /etc/logrotate.d/seit
```

## �� Backup & Recovery

### Database Backup
```bash
# PostgreSQL backup
docker-compose exec postgres pg_dump -U seit_user seit_db > backup.sql

# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec postgres pg_dump -U seit_user seit_db > "backup_${DATE}.sql"
gzip "backup_${DATE}.sql"
```

### Environment Backup
```bash
# Backup environment configuration
cp .env .env.backup.$(date +%Y%m%d)

# Backup Docker volumes
docker run --rm -v seit_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

## 🚀 Performance Optimization

### Production Optimizations
```dockerfile
# Multi-stage build for minimal production image
FROM node:18-alpine as builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

### Caching Strategy
```python
# Redis caching configuration
CACHE_SETTINGS = {
    'sensor_data': 300,      # 5 minutes
    'satellite_tiles': 3600, # 1 hour
    'analysis_results': 1800 # 30 minutes
}
```

### Database Indexing
```sql
-- Critical indexes for performance
CREATE INDEX idx_sensor_data_location ON sensor_data(latitude, longitude);
CREATE INDEX idx_sensor_data_timestamp ON sensor_data(timestamp);
CREATE INDEX idx_sensor_data_source ON sensor_data(source);
```

## 🔧 Troubleshooting

### Common Issues

#### 1. "vite: not found" Error
```bash
# Install dependencies
pnpm install

# Or install globally
npm install -g vite
```

#### 2. Database Connection Issues
```bash
# Check database status
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

#### 3. NASA API Authentication Errors
```bash
# Validate NASA token
curl -H "Authorization: Bearer $NASA_EARTHDATA_TOKEN" \
  https://cmr.earthdata.nasa.gov/search/collections.json

# Check token expiration
# NASA tokens typically expire every 60 days
```

#### 4. Memory Issues
```bash
# Monitor memory usage
docker stats

# Adjust memory limits in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

### Performance Issues
```bash
# Check API response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/health

# Monitor Redis cache hit rates
docker-compose exec redis redis-cli info stats

# Check database performance
docker-compose exec postgres pg_stat_statements
```

## 📞 Support

### Getting Help
- **Documentation**: Check our comprehensive docs first
- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and community support
- **Email**: support@biela.dev for deployment assistance

### Professional Support
For enterprise deployments, professional support is available:
- **Setup Assistance**: Guided deployment and configuration
- **Custom Integration**: API customization and data source integration
- **Performance Tuning**: Optimization for high-traffic environments
- **Training**: Team training on platform administration

---

**🌟 Ready to deploy your air quality monitoring platform!**

For additional assistance, consult our [GitHub Discussions](https://github.com/yourusername/seit/discussions) or contact support@biela.dev.
