# Contributing to coldpack

Thank you for your interest in contributing to coldpack! This document provides guidelines for contributing to the project.

## Quick Start

1. **Fork and Clone**
   ```bash
   git clone https://github.com/rxchi1d/coldpack.git
   cd coldpack
   ```

2. **Set up Development Environment**
   ```bash
   # Install uv (if not already installed)
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Create virtual environment and install dependencies
   uv sync --dev

   # Activate virtual environment
   source .venv/bin/activate  # Unix/macOS
   # or .venv\Scripts\activate  # Windows
   ```

3. **Install Pre-commit Hooks**
   ```bash
   # Install and set up pre-commit hooks
   uv run pre-commit install

   # Run initial check on all files
   uv run pre-commit run --all-files
   ```

4. **Run Quality Checks (Automated)**
   ```bash
   # Pre-commit hooks will run automatically on commit
   # To run manually before committing:
   uv run pre-commit run --all-files

   # Manual quality checks (backup method):
   uv run ruff format .        # Format code
   uv run ruff check --fix .   # Lint and fix issues
   uv run mypy src/            # Type checking
   uv run pytest              # Run tests
   ```

## Development Workflow

### Making Changes

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow the code style and architecture patterns
   - Add tests for new functionality
   - Update documentation if needed

3. **Test Your Changes**
   ```bash
   # Option 1: Automated via pre-commit (recommended)
   git add .
   git commit -m "your message"  # Hooks run automatically

   # Option 2: Manual quality checks
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy src/
   uv run pytest
   ```

4. **Commit Your Changes**
   - Follow our [commit message convention](#commit-message-convention)
   - Make atomic commits with clear purposes

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Style

- **Line Length**: 88 characters maximum
- **Linting**: Use Ruff with project configuration
- **Type Hints**: Required for all Python code
- **Import Sorting**: Automated by Ruff
- **Formatting**: Black-compatible formatting via Ruff

### Testing

- **Unit Tests**: Required for all new functionality
- **Integration Tests**: For archive processing and cross-platform compatibility
- **Test Coverage**: Aim for high coverage on critical paths
- **Cross-Platform**: Tests must pass on Python 3.9-3.13

## Commit Message Convention

We follow **Conventional Commits** for automated release notes generation.

### Format

```
<type>(<scope>): <description>    ← First line (50-72 chars max)

[optional body]                   ← Detailed explanation (wrap at 72 chars)

[optional footer(s)]              ← Breaking changes, issue references
```

**Important Notes:**
- **First line**: Used by GitHub for auto-generated release notes
- **Body**: Detailed explanation for complex changes (not used in release notes)
- **Footer**: Breaking changes and issue references

### Types

- **feat**: New feature (MINOR version)
- **fix**: Bug fix (PATCH version)
- **docs**: Documentation changes
- **style**: Code formatting (no functional changes)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Test-related changes
- **chore**: Build tools or auxiliary tool changes
- **ci**: CI/CD changes

### Examples

**❌ Bad:**
```bash
git commit -m "feat: add compression support"
git commit -m "fix: Windows bug"
git commit -m "docs: update readme"
```

**✅ Good First Lines:**
```bash
git commit -m "feat: add zstd compression with dynamic level adjustment"
git commit -m "fix: resolve PAR2 generation on Windows systems with spaces in paths"
git commit -m "docs: add comprehensive cold storage workflow guide"
git commit -m "perf: optimize memory usage for large archive processing"
```

**✅ Good Multi-line Commits:**
```bash
git commit -m "feat: add async archive operations with progress callbacks

This commit introduces comprehensive async support including:
- Progress callback mechanism for real-time updates
- Batch operations for multiple archives
- Memory-efficient streaming for large files
- Cross-platform compatibility testing

The implementation maintains backward compatibility while
providing significant performance improvements for large-scale
cold storage operations."

git commit -m "fix: resolve PAR2 generation on Windows systems with spaces in paths

The previous implementation failed when archive paths contained
spaces due to incorrect subprocess argument handling. This fix:

- Properly quotes paths in subprocess calls
- Adds comprehensive path validation
- Includes test cases for paths with spaces
- Maintains compatibility with existing workflows

Fixes #42"
```

### Breaking Changes

Use `BREAKING CHANGE:` in the commit body for major version changes:
```bash
git commit -m "feat!: redesign API for better cold storage workflow

BREAKING CHANGE: Archiver.create() now returns verification results instead of boolean"
```

### Scope (Optional)

Specify the affected area:
```bash
git commit -m "feat(archiver): add PAR2 redundancy generation"
git commit -m "fix(cli): resolve version display format"
git commit -m "docs(readme): add installation troubleshooting"
```

## Pull Request Process

1. **PR Title Convention**

   **IMPORTANT**: PR titles are used for release notes generation and must follow the same convention as commit messages:

   ```
   <type>(<scope>): <description>
   ```

   **Examples:**
   ```
   feat: add async archive operations with progress callbacks
   fix: resolve PAR2 generation on Windows systems
   docs: add comprehensive cold storage workflow guide
   perf: optimize memory usage for large archive processing
   ```

   **Why this matters:**
   - PR titles appear directly in release notes
   - Automatic labeling based on PR title
   - Semantic version determination (feat = minor, fix = patch)

2. **Pre-submission Checklist**
   - [ ] Pre-commit hooks are installed: `uv run pre-commit install`
   - [ ] PR title follows conventional format
   - [ ] All quality checks pass (automatically via pre-commit or manually)
   - [ ] Tests are added for new functionality
   - [ ] Documentation is updated if needed
   - [ ] Commit messages follow convention
   - [ ] No TODO/FIXME comments left unresolved

3. **PR Description**
   - Clearly describe what changes were made
   - Reference any related issues
   - Include testing information for archive formats
   - List any breaking changes

4. **Review Process**
   - All CI checks must pass
   - Code review by maintainers
   - Address feedback promptly
   - Squash commits if requested

## Development Environment Details

### Dependencies

- **Runtime**: Python 3.9+ support required
- **Development**: uv for dependency management
- **Testing**: pytest for unit and integration tests
- **Linting**: ruff for code quality
- **Type Checking**: mypy for static analysis

### Project Structure

```
coldpack/
├── src/
│   └── coldpack/
│       ├── __init__.py         # Main API exports
│       ├── cli.py              # CLI tool implementation (cpack)
│       ├── core/
│       │   ├── archiver.py     # Archive creation and compression
│       │   ├── extractor.py    # Archive extraction
│       │   ├── verifier.py     # Integrity verification
│       │   └── repairer.py     # PAR2 repair functionality
│       ├── utils/              # Utility functions
│       └── config/             # Configuration management
├── tests/                      # Test suite
├── docs/                       # Documentation
└── .github/workflows/          # CI/CD configuration
```

### Cold Storage Features

coldpack focuses on reliable long-term archive storage:
- **Standardized Format**: tar.zst with consistent compression
- **Dual Verification**: SHA-256 + BLAKE3 hash verification
- **PAR2 Redundancy**: Error correction for long-term storage
- **Cross-platform**: Consistent behavior across operating systems

## Release Process

Releases are automated through GitHub Actions:
1. **Tag Creation**: Push a version tag (e.g., `v0.1.0`)
2. **Automated Build**: Python wheels are built and tested
3. **PyPI Publication**: Wheels are published to PyPI via OIDC
4. **GitHub Release**: Release notes are auto-generated from PR titles

## Getting Help

- **Issues**: Report bugs or request features via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check README.md and docs/ directory
- **Development Guide**: See CLAUDE.md for detailed development instructions

## Code of Conduct

Please be respectful and professional in all interactions. We follow the standard open-source community guidelines for inclusive collaboration.

## Security

If you discover a security vulnerability, please follow our [Security Policy](.github/SECURITY.md) and report it privately rather than creating a public issue.

## License

By contributing to coldpack, you agree that your contributions will be licensed under the same terms as the project (BSD-3-Clause).
