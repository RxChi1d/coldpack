# coldpack

[![PyPI version](https://badge.fury.io/py/coldpack.svg)](https://badge.fury.io/py/coldpack)
[![Python Support](https://img.shields.io/pypi/pyversions/coldpack.svg)](https://pypi.org/project/coldpack/)
[![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/rxchi1d/coldpack)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI Status](https://github.com/rxchi1d/coldpack/workflows/CI/badge.svg)](https://github.com/rxchi1d/coldpack/actions)

[English](README.md) | [繁體中文](README.zh-tw.md)

A Python CLI tool for creating standardized 7z archives for long-term data storage with integrity verification, PAR2 recovery, and cross-platform compatibility.

## Overview

coldpack is a command-line tool for creating standardized cold storage archives. It converts various source formats (directories, zip, tar, etc.) into 7z archives with integrated verification and recovery mechanisms designed for long-term data preservation.

## Features

### Core Functionality
- **7z-only output**: Converts various input formats to standardized 7z archives
- **Adaptive compression**: Automatically selects compression parameters based on file size
- **Command-line interface**: Simple CLI commands for archive management

### Available Commands
- **`cpack create`** - Create 7z cold storage archives
- **`cpack extract`** - Extract archives with parameter restoration
- **`cpack verify`** - Verify archive integrity using multiple methods
- **`cpack repair`** - Repair corrupted archives using PAR2 recovery
- **`cpack info`** - Display archive metadata
- **`cpack list`** - List archive contents with filtering options

### Verification and Recovery
- **Multiple verification layers**: 7z integrity, SHA-256, BLAKE3, and PAR2
- **Dual hash algorithms**: SHA-256 for compatibility, BLAKE3 for performance
- **PAR2 recovery files**: 10% redundancy for error correction
- **Metadata preservation**: Stores compression parameters in metadata.toml

### Cross-Platform Support
- **Operating systems**: Windows, macOS, Linux
- **System file handling**: Automatically excludes platform-specific files (.DS_Store, Thumbs.db)
- **Unicode support**: Handles international filenames correctly with automatic compatibility
- **Progress tracking**: Real-time progress display during operations

For detailed installation and usage instructions, see [Installation Guide](docs/INSTALLATION.md) and [CLI Reference](docs/CLI_REFERENCE.md).

## Quick Start

### Installation

```bash
# Using pip (recommended)
pip install coldpack

# Using uv
uv add coldpack
```

**Requirements**: Python 3.9+ | Windows, macOS, Linux

For detailed installation instructions including development setup, see [Installation Guide](docs/INSTALLATION.md).

### Basic Usage

```bash
# Create 7z cold storage archive
cpack create /path/to/documents --output-dir ~/cold-storage

# Extract with automatic parameter recovery
cpack extract ~/cold-storage/documents.7z --output-dir ~/restored

# Verify 4-layer integrity
cpack verify ~/cold-storage/documents.7z

# Advanced file listing with filtering
cpack list ~/cold-storage/documents.7z --filter "*.pdf" --limit 10
```

### Advanced Usage

```bash
# Custom compression levels (0-9) with memory limit
cpack create large-dataset/ --level 9 --dict 512m --memory-limit 2g --output-dir ~/archives

# Memory-constrained compression for limited systems
cpack create documents/ --memory-limit 512m --output-dir ~/archives

# Pre-verification before extraction
cpack extract suspicious-archive.7z --verify --output-dir ~/safe-extraction

# Repair corrupted files using PAR2
cpack repair ~/cold-storage/damaged-archive.7z

# Display metadata information
cpack info ~/cold-storage/documents.7z
```

See [Usage Examples](docs/EXAMPLES.md) for more use cases and workflows.

## Technical Specifications

### Supported Input Formats
- **Directories**: Any filesystem directory structure
- **Archive Formats**: 7z, zip, rar, tar, tar.gz, tar.bz2, tar.xz, tar.zst

### Output Structure
```
archive-name/
├── archive-name.7z              # Main 7z archive
├── archive-name.7z.sha256       # SHA-256 hash
├── archive-name.7z.blake3       # BLAKE3 hash
├── archive-name.7z.par2         # PAR2 recovery files
└── metadata/
    └── metadata.toml            # Complete archive metadata
```

### Verification System

1. **7z Integrity**: Native 7z archive structure validation
2. **SHA-256**: Cryptographic hash verification (legacy compatibility)
3. **BLAKE3**: Modern high-performance cryptographic hash
4. **PAR2 Recovery**: Error correction with 10% redundancy

### Compression Optimization

| File Size Range | Compression Level | Dictionary Size | Use Case |
|-----------------|-------------------|-----------------|----------|
| < 256 KiB | Level 1 | 128k | Minimal resources |
| 256 KiB – 1 MiB | Level 3 | 1m | Light compression |
| 1 – 8 MiB | Level 5 | 4m | Balanced performance |
| 8 – 64 MiB | Level 6 | 16m | Good compression |
| 64 – 512 MiB | Level 7 | 64m | High compression |
| 512 MiB – 2 GiB | Level 9 | 256m | Maximum compression |
| > 2 GiB | Level 9 | 512m | Maximum efficiency |

For detailed architecture documentation and configuration options, see [Architecture Guide](docs/ARCHITECTURE.md).

## Development & Contributing

### Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/rxchi1d/coldpack.git
cd coldpack
uv sync --dev
source .venv/bin/activate
```

### Quality Assurance

```bash
# Code formatting and linting
uv run ruff format . && uv run ruff check --fix .

# Type checking and testing
uv run mypy src/ && uv run pytest
```

**Development Standards**: Comprehensive test suite, ruff formatting, MyPy type checking, cross-platform CI/CD

See [CLAUDE.md](CLAUDE.md) for complete development instructions.


## License & Support

**License**: MIT - See [LICENSE](LICENSE) for details

**Documentation**:
- [Installation Guide](docs/INSTALLATION.md) - Setup instructions
- [CLI Reference](docs/CLI_REFERENCE.md) - Command documentation
- [Usage Examples](docs/EXAMPLES.md) - Use cases and workflows
- [Architecture Guide](docs/ARCHITECTURE.md) - Technical implementation details

**Support**: [GitHub Issues](https://github.com/rxchi1d/coldpack/issues) | [Discussions](https://github.com/rxchi1d/coldpack/discussions)
