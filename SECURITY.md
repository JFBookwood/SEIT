# Security Policy

## �� Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Yes             |
| < 1.0   | ❌ No              |

## 🚨 Reporting a Vulnerability

### Where to Report
**Do NOT open public issues for security vulnerabilities.**

Instead, please report security issues by emailing: **security@biela.dev**

### What to Include
When reporting security vulnerabilities, please include:

1. **Description**: Clear description of the vulnerability
2. **Impact**: What could an attacker accomplish?
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Proof of Concept**: Code or screenshots demonstrating the vulnerability
5. **Suggested Fix**: If you have ideas for remediation

### Response Timeline
- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution**: Within 30 days for critical issues

## 🛡️ Security Measures

### Current Security Implementations

#### API Security
- **Authentication**: JWT-based authentication for admin endpoints
- **Authorization**: Role-based access control
- **Input Validation**: Comprehensive validation for all endpoints
- **Rate Limiting**: API rate limiting to prevent abuse
- **CORS**: Proper cross-origin resource sharing configuration

#### Data Protection
- **Environment Variables**: All secrets stored as environment variables
- **NASA Token Security**: NASA Earthdata token stored server-side only
- **SQL Injection**: Parameterized queries via SQLAlchemy
- **XSS Protection**: Input sanitization and CSP headers

#### Infrastructure Security
- **HTTPS**: TLS encryption for all communications
- **Container Security**: Multi-stage Docker builds with minimal attack surface
- **Dependency Scanning**: Regular vulnerability scanning of dependencies
- **Security Headers**: Comprehensive security headers implementation

### Environmental Data Security
- **NASA Compliance**: Proper handling of NASA Earthdata credentials
- **API Key Protection**: All external API keys stored securely
- **Data Attribution**: Proper attribution for all data sources
- **Usage Logging**: Audit trails for NASA API usage

## �� Security Configuration

### Required Environment Variables
```bash
# Critical security variables
SECRET_KEY=generate-strong-random-key-here
NASA_EARTHDATA_TOKEN=your-nasa-token-here

# Optional API keys (use mock data if not provided)
PURPLEAIR_API_KEY=your-purpleair-key
OPENWEATHER_API_KEY=your-openweather-key
```

### Production Security Checklist
- [ ] All environment variables configured
- [ ] HTTPS enabled with valid certificates
- [ ] Database access restricted to application only
- [ ] NASA Earthdata token permissions properly scoped
- [ ] Regular security updates applied
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures tested

## �� Security Don'ts

### Never Do This:
1. **Hardcode secrets** in source code
2. **Expose NASA tokens** in client-side JavaScript
3. **Disable CORS** without understanding implications
4. **Skip input validation** on user-provided data
5. **Store passwords** in plain text
6. **Ignore security warnings** from dependency scanners

## �� Security Best Practices

### For Contributors
1. **Review dependencies** for known vulnerabilities
2. **Validate all inputs** from users and external APIs
3. **Use parameterized queries** for database operations
4. **Follow principle of least privilege** for API access
5. **Test security measures** before submitting PRs

### For Deployments
1. **Use HTTPS** in production environments
2. **Rotate secrets** regularly (NASA tokens, JWT keys)
3. **Monitor access logs** for suspicious activity
4. **Keep dependencies updated** with security patches
5. **Implement proper backup** and disaster recovery

## 🔍 Vulnerability Disclosure

### Public Disclosure Timeline
1. **Day 0**: Vulnerability reported privately
2. **Day 1-7**: Initial assessment and response
3. **Day 7-30**: Development and testing of fix
4. **Day 30**: Public disclosure with fixed version

### Recognition
We believe in recognizing security researchers who help improve SEIT:
- **Security Hall of Fame**: Listed in SECURITY.md (with permission)
- **CVE Assignment**: For significant vulnerabilities
- **Acknowledgment**: In release notes and changelog

## 📞 Contact Information

- **Security Email**: security@biela.dev
- **General Contact**: support@biela.dev
- **Project Maintainer**: [@yourusername](https://github.com/yourusername)

---

**Thank you for helping keep SEIT secure!** 🛡️
