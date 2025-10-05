# 🚀 SEIT Local Development Setup (No Docker)

## Quick Start (Recommended)

### Windows Users:
```bash
# Run this single command:
quick-start.bat
```

### Mac/Linux Users:
```bash
# Make executable and run:
chmod +x quick-start.sh
./quick-start.sh
```

This will automatically start both backend and frontend services.

---

## Manual Setup (If Quick Start Fails)

### Step 1: Backend Setup

1. **Navigate to backend:**
```bash
cd backend
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Start backend:**
```bash
python startup.py
```

**Expected Output:**
```
🔧 Setting up SEIT Backend...
✅ All required packages are installed
✅ Database initialized successfully
�� Starting SEIT Backend Server...
📍 Server will be available at: http://localhost:8000
📖 API Documentation: http://localhost:8000/docs
```

### Step 2: Frontend Setup

1. **Open new terminal in project root**

2. **Install dependencies:**
```bash
pnpm install
```

3. **Start frontend:**
```bash
pnpm dev
```

**Expected Output:**
```
  VITE v4.3.9  ready in 1234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h to show help
```

---

## Verification Steps

### 1. Test Backend Health
```bash
curl http://localhost:8000/api/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "service": "SEIT Backend",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0"
}
```

### 2. Test Sensor Data Endpoint
```bash
curl http://localhost:8000/api/sensors/enhanced-integration
```

### 3. Open Frontend
Open your browser to: **http://localhost:5173**

You should see the SEIT dashboard loading with sensor data.

---

## Troubleshooting

### ❌ Backend Won't Start

**Error: "Module not found"**
```bash
cd backend
pip install -r requirements.txt
```

**Error: "Port 8000 in use"**
```bash
# Kill process on port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux:
lsof -ti:8000 | xargs kill
```

### ❌ Frontend Won't Connect

**Check API URL in browser console:**
- Open DevTools → Console
- Look for errors mentioning `localhost:8000`

**Fix CORS Issues:**
Make sure backend `.env` file has:
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:4173
```

### ❌ No Sensor Data Loading

**The app will show mock data if:**
- No API keys are provided (normal for demo)
- External APIs are down (fallback working correctly)

**To use real data, add to backend/.env:**
```env
PURPLEAIR_API_KEY=your_key_here
EARTHDATA_USERNAME=your_username
EARTHDATA_PASSWORD=your_password
```

---

## URLs After Setup

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

---

## Development Workflow

1. **Backend changes**: Server auto-reloads with `reload=True`
2. **Frontend changes**: Vite HMR updates instantly  
3. **API testing**: Use `/docs` endpoint for interactive testing

The app includes comprehensive error handling and will show friendly messages if external APIs are unavailable, so you can develop and test locally even without API keys.
