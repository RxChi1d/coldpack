# Local CI Scripts

This directory contains scripts to simulate CI workflows locally, helping you catch issues before pushing to the remote repository.

## Scripts Overview

### 1. `quick-check.sh` - Fast Development Checks

A lightweight script for frequent local testing during development.

**What it does:**
- 🔧 Sets up development environment
- 📝 Checks code formatting (ruff format)
- 🔍 Runs linting checks (ruff check)  
- 🎯 Performs type checking (mypy)

**Usage:**
```bash
./scripts/quick-check.sh
```

**When to use:**
- Before each commit
- During active development
- Quick validation of code changes

### 2. `ci-local.sh` - Complete CI Simulation

A comprehensive script that mimics the full remote CI workflow.

**What it does:**
- ✅ All quick checks (delegates to `quick-check.sh`)
- 🔒 Security scanning (bandit + safety)
- 🧪 Comprehensive testing with coverage
- 🐍 Python version compatibility checks
- 📊 Generates coverage reports
- 🧹 Cleans up temporary files

**Usage:**
```bash
# Full CI simulation
./scripts/ci-local.sh

# Quick checks only
./scripts/ci-local.sh --quick-only

# Keep temporary files for inspection
./scripts/ci-local.sh --no-cleanup

# Show help
./scripts/ci-local.sh --help
```

**When to use:**
- Before pushing to remote repository
- Before creating pull requests
- When you want comprehensive local validation

## Expected Output

### Successful Run
```
✅ All CI checks passed!
Your code is ready to push to remote repository.

Generated reports:
  📊 Coverage XML: coverage.xml
  📊 Coverage HTML: htmlcov/index.html
```

### Failed Checks
```
❌ Some CI checks failed!
Please fix the issues above before pushing to remote.
```

## Generated Files

The scripts may generate the following files:

- `coverage.xml` - Coverage report in XML format
- `htmlcov/` - HTML coverage report directory
- `bandit-report.json` - Security scan results (temporary)
- `safety-report.json` - Dependency vulnerability report (temporary)

## Integration with Development Workflow

### Recommended Workflow

1. **During Development:**
   ```bash
   # Make changes to code
   ./scripts/quick-check.sh
   # Fix any issues and repeat
   ```

2. **Before Committing:**
   ```bash
   ./scripts/quick-check.sh
   git add .
   git commit -m "your commit message"
   ```

3. **Before Pushing:**
   ```bash
   ./scripts/ci-local.sh
   # If all passes:
   git push
   ```

### Git Hooks Integration

You can integrate these scripts with git hooks:

**Pre-commit hook** (`.git/hooks/pre-commit`):
```bash
#!/bin/bash
./scripts/quick-check.sh
```

**Pre-push hook** (`.git/hooks/pre-push`):
```bash
#!/bin/bash
./scripts/ci-local.sh --quick-only
```

## Troubleshooting

### Common Issues

1. **Script Permission Denied**
   ```bash
   chmod +x scripts/*.sh
   ```

2. **uv Not Found**
   - Install uv: https://docs.astral.sh/uv/getting-started/installation/

3. **Python Version Issues**
   - Ensure Python >= 3.9 is installed
   - The scripts will work with any single Python version locally

4. **Dependencies Not Found**
   - Run: `uv sync --dev`
   - Ensure you're in the project root directory

### Performance Tips

- Use `--quick-only` for faster feedback during development
- The full CI simulation may take 2-5 minutes depending on your system
- Coverage HTML reports can be opened in browser for detailed analysis

## Contributing

When modifying these scripts:

1. Keep the modular design (quick-check.sh as a standalone component)
2. Maintain colored output for better UX
3. Ensure proper error handling and exit codes
4. Update this README if adding new functionality

## CI Parity

These scripts are designed to closely match the remote CI workflow defined in `.github/workflows/ci.yml`. Any changes to the remote CI should be reflected in these local scripts to maintain parity.