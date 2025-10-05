# NASA Earthdata Token Rotation Guide

## 🔐 Security Overview

NASA Earthdata tokens are critical security credentials that must be:
- Stored securely as environment variables (server-side only)
- Rotated regularly (every 45-60 days)
- Never exposed in client-side code or logs
- Monitored for usage and expiration

## 📋 Token Rotation Process

### Step 1: Generate New Token

1. **Login to NASA Earthdata URS**
   - Visit: https://urs.earthdata.nasa.gov/
   - Login with your Earthdata credentials

2. **Navigate to Applications**
   - Go to "My Account" → "Applications"
   - Click "Generate Token" or "Regenerate Token"

3. **Copy New Token**
   - Copy the new JWT token (starts with "eyJ")
   - Store securely (do not share or commit to git)

### Step 2: Update Environment Variable

#### Development Environment
```bash
# Update .env file
NASA_EARTHDATA_TOKEN=your_new_token_here
```

#### Production Deployment

**Docker Compose:**
```bash
# Update .env file and restart services
docker-compose down
# Edit .env file with new token
docker-compose up -d
```

**Cloud Platforms:**
- **Render.com**: Update environment variable in dashboard
- **Railway**: Use `railway variables set NASA_EARTHDATA_TOKEN=new_token`
- **Vercel**: Update environment variable in project settings
- **AWS/GCP/Azure**: Update environment variable in container service

### Step 3: Validate New Token

1. **Use Admin Interface**
   - Go to Admin → NASA Integration
   - Click "Validate Token"
   - Verify token status shows "Valid"

2. **API Validation**
   ```bash
   curl -X POST http://localhost:8000/api/admin/nasa/validate-token
   ```

3. **Test API Access**
   - Click "Test API Access" in admin interface
   - Verify all NASA services show "accessible"

## �� Security Best Practices

### Environment Variable Security
```bash
# ✅ CORRECT - Environment variable
NASA_EARTHDATA_TOKEN=eyJ0eXAiOiJKV1Q...

# ❌ WRONG - Never hardcode in source code
const token = "eyJ0eXAiOiJKV1Q...";

# ❌ WRONG - Never commit to version control
git add .env  # Don't do this!
```

### Server-Side Only Usage
```python
# ✅ CORRECT - Server-side authentication
headers = nasa_auth_service.get_auth_headers()
response = await session.get(nasa_url, headers=headers)

# ❌ WRONG - Never send to client
return {"nasa_token": os.getenv("NASA_EARTHDATA_TOKEN")}
```

### Monitoring and Logging
```python
# ✅ CORRECT - Log usage without exposing token
logger.info(f"NASA API call: {service} -> {status_code}")

# ❌ WRONG - Never log the actual token
logger.info(f"Using token: {token}")
```

## 📊 Monitoring Token Health

### Automated Checks
- **Daily validation**: Automatic token health checks
- **Expiration warnings**: Alerts when token expires within 30 days
- **Usage monitoring**: Track API calls and response patterns
- **Error detection**: Identify authentication failures

### Admin Dashboard Monitoring
1. **Token Status**: Current validity and expiration date
2. **API Usage**: Request counts and success rates
3. **Service Health**: Individual NASA service accessibility
4. **Error Tracking**: Failed requests and authentication issues

## 🛠️ Troubleshooting

### Token Validation Fails
```bash
# Check token format (should start with "eyJ")
echo $NASA_EARTHDATA_TOKEN | head -c 10

# Verify token is not expired
curl -X POST http://localhost:8000/api/admin/nasa/validate-token
```

### API Access Issues
1. **Check token expiration**: Tokens expire every 60 days
2. **Verify network connectivity**: Ensure server can reach *.earthdata.nasa.gov
3. **Check URS account status**: Ensure account is active and approved
4. **Review EULA compliance**: Some datasets require additional agreements

### Common Error Responses

| Status Code | Meaning | Solution |
|-------------|---------|----------|
| 401 | Unauthorized | Token expired or invalid - rotate token |
| 403 | Forbidden | Account lacks permissions - check EULA agreements |
| 429 | Rate Limited | Too many requests - implement backoff |
| 500 | Server Error | NASA service issue - retry later |

## 📞 Support Resources

- **NASA Earthdata Help**: https://earthdata.nasa.gov/learn/user-resources
- **URS Account Management**: https://urs.earthdata.nasa.gov/
- **GIBS Documentation**: https://gibs.earthdata.nasa.gov/
- **Harmony Service**: https://harmony.earthdata.nasa.gov/

## 🔄 Automation Scripts

### Token Expiration Check
```python
# Add to your monitoring scripts
import os
import json
import base64
from datetime import datetime, timezone

def check_token_expiration():
    token = os.getenv("NASA_EARTHDATA_TOKEN")
    if not token:
        return "No token configured"
    
    try:
        payload = token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        
        exp_timestamp = decoded.get('exp', 0)
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        days_remaining = (expires_at - datetime.now(timezone.utc)).days
        
        if days_remaining <= 0:
            return "CRITICAL: Token expired"
        elif days_remaining <= 7:
            return f"WARNING: Token expires in {days_remaining} days"
        else:
            return f"OK: Token expires in {days_remaining} days"
            
    except Exception as e:
        return f"ERROR: Could not parse token - {e}"
```

### Monitoring Alert Integration
```bash
# Example cron job for token monitoring
# Run daily at 09:00 UTC
0 9 * * * /path/to/check_nasa_token.sh >> /var/log/nasa_token_check.log 2>&1
```

## ⚠️ Important Notes

1. **Token Privacy**: NASA tokens are personally identifiable and should be treated as sensitive credentials
2. **Account Responsibility**: Each token is tied to an individual NASA Earthdata account
3. **Usage Compliance**: Respect NASA's data usage policies and rate limits
4. **Backup Plans**: Maintain fallback mechanisms when NASA services are unavailable
5. **Documentation**: Keep rotation logs for audit compliance

Following these procedures ensures secure, compliant, and reliable NASA Earthdata integration.
