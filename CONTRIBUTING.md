# Contributing to SEIT

Thank you for your interest in contributing to SEIT! This document provides guidelines for contributing to the Space Environmental Impact Tracker project.

## 🤝 How to Contribute

### 1. Fork the Repository

```bash
git clone https://github.com/yourusername/seit.git
cd seit
```

### 2. Set Up Development Environment

#### Prerequisites
- Node.js 18+ and pnpm
- Python 3.11+
- Docker (optional)

#### Quick Setup
```bash
# Install frontend dependencies
pnpm install

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Development Workflow

#### Frontend Development
```bash
# Start development server
pnpm dev

# Run tests
pnpm test

# Check code formatting
pnpm format
```

#### Backend Development
```bash
cd backend

# Start FastAPI server
python main.py

# Run tests
pytest

# Check code style
black . && flake8
```

## 📋 Types of Contributions

### 🐛 Bug Reports
When filing bug reports, please include:
- **Environment**: OS, browser, Node.js version
- **Steps to reproduce**: Clear, numbered steps
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Screenshots**: If applicable

### 💡 Feature Requests
For new features, please include:
- **Problem statement**: What problem does this solve?
- **Proposed solution**: How would you like it implemented?
- **Use cases**: Who would benefit from this feature?
- **Implementation ideas**: Technical approach (if you have one)

### 🔧 Code Contributions

#### Branch Naming
- `feature/description` - For new features
- `fix/description` - For bug fixes
- `docs/description` - For documentation updates
- `refactor/description` - For code refactoring

#### Commit Messages
Follow conventional commits format:
```
type(scope): description

feat(map): add heatmap uncertainty visualization
fix(api): resolve NASA GIBS authentication issue
docs(readme): update installation instructions
```

#### Pull Request Process
1. Create a feature branch from `main`
2. Make your changes with appropriate tests
3. Update documentation if needed
4. Ensure all tests pass
5. Submit a pull request with:
   - Clear description of changes
   - Link to related issues
   - Screenshots for UI changes

## 🧪 Testing Guidelines

### Frontend Testing
```bash
# Run all tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Generate coverage report
pnpm test:coverage
```

### Backend Testing
```bash
cd backend

# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=api tests/

# Run specific test files
pytest tests/test_sensors.py -v
```

### Integration Testing
```bash
# Start both services and run integration tests
docker-compose -f docker-compose.test.yml up --build
```

## 📏 Code Standards

### Frontend Standards
- **Framework**: React 18 with functional components and hooks
- **Styling**: Tailwind CSS with Relume components
- **Icons**: Lucide React (no Font Awesome)
- **File Organization**: Components in `/src/components/[Feature]/`
- **State Management**: React hooks + Zustand for global state
- **API Calls**: Custom hooks with error handling

### Backend Standards
- **Framework**: FastAPI with async/await
- **Database**: SQLAlchemy with Alembic migrations
- **Code Style**: Black formatter + flake8 linting
- **API Design**: RESTful endpoints with OpenAPI documentation
- **Error Handling**: Proper HTTP status codes and error messages
- **Security**: Environment variables for secrets, input validation

### General Standards
- **File Size**: Maximum 250 lines per file
- **Documentation**: Inline comments for complex logic
- **Type Hints**: TypeScript for frontend, Python type hints for backend
- **Environment**: Support for development, testing, and production

## 🌍 Environmental Data Guidelines

### NASA Earthdata Integration
- **Authentication**: Server-side only, never expose tokens
- **Rate Limiting**: Respect NASA API limits (1-2 requests/second)
- **Caching**: Cache satellite products with appropriate TTL
- **Attribution**: Proper credit for NASA data sources

### Sensor Data Quality
- **Validation**: Coordinate validation, range checks
- **Harmonization**: Consistent field naming across sources
- **Calibration**: Linear models with uncertainty quantification
- **QC Flags**: Transparent quality control documentation

### Scientific Accuracy
- **Interpolation**: IDW and kriging with uncertainty estimates
- **Cross-Validation**: Leave-one-site-out validation metrics
- **Documentation**: Clear methodology and limitation descriptions
- **Reproducibility**: Version control for calibration parameters

## 🎯 Development Priorities

### High Priority
1. **Data Quality**: Accuracy and reliability of environmental measurements
2. **Performance**: Fast loading and responsive user interface
3. **Security**: Proper handling of API keys and user data
4. **Documentation**: Clear setup and usage instructions

### Medium Priority
1. **New Features**: Additional data sources and analysis methods
2. **UI/UX**: Enhanced visualizations and user experience
3. **Testing**: Expanded test coverage and integration tests
4. **Optimization**: Performance improvements and caching strategies

### Low Priority
1. **Refactoring**: Code organization and architecture improvements
2. **Developer Tools**: Enhanced development workflow and tooling
3. **Documentation**: Advanced tutorials and API examples

## 📞 Getting Help

### Questions and Discussion
- **GitHub Discussions**: For general questions and feature discussions
- **Issues**: For specific bugs or feature requests
- **Email**: support@biela.dev for private inquiries

### Resources
- **API Documentation**: `/docs` endpoint when running locally
- **Project Wiki**: Detailed technical documentation
- **Code Examples**: Check `/examples` directory for usage patterns

## 🏆 Recognition

Contributors will be recognized in:
- **Contributors section** of the README
- **Changelog** for significant contributions
- **GitHub contributors graph**
- **Special thanks** in release notes

## 📜 Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:
- **Be respectful** in all interactions
- **Be constructive** in feedback and criticism
- **Be collaborative** and help others learn
- **Be patient** with questions and different skill levels

Thank you for contributing to SEIT! 🚀
