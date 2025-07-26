# coldpack

[![PyPI version](https://badge.fury.io/py/coldpack.svg)](https://badge.fury.io/py/coldpack)
[![Python Support](https://img.shields.io/pypi/pyversions/coldpack.svg)](https://pypi.org/project/coldpack/)
[![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/rxchi1d/coldpack)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI Status](https://github.com/rxchi1d/coldpack/workflows/CI/badge.svg)](https://github.com/rxchi1d/coldpack/actions)

[English](README.md) | [繁體中文](README.zh-tw.md)

> **Professional 7z Cold Storage Solution with Revolutionary Architecture**
>
> Advanced CLI tool for creating standardized 7z archives with comprehensive verification, PAR2 recovery, and intelligent cross-platform compatibility.

## Overview

coldpack is a professional-grade CLI tool that revolutionizes cold storage with its **7z-exclusive architecture**. Designed for long-term data preservation, it transforms various archive formats into standardized 7z cold storage with comprehensive verification and recovery systems.

**Key Innovation**: Complete architectural redesign focusing exclusively on 7z format, providing the industry's most sophisticated cold storage solution with 7-tier dynamic compression optimization.

## Features

### 🚀 Revolutionary 7z-Exclusive Architecture
- **Professional 7z-Only Output**: Streamlined architecture optimized exclusively for 7z cold storage
- **7-Tier Dynamic Compression**: Intelligent parameter selection (< 256KB to > 2GB file sizes)
- **Simplified CLI Interface**: No format confusion - pure 7z cold storage workflow

### 🔧 Complete CLI Command Suite
- **`cpack create`** - Create 7z cold storage with dynamic optimization
- **`cpack extract`** - Extract with automatic parameter recovery and pre-verification
- **`cpack verify`** - 4-layer integrity verification with auto-discovery
- **`cpack repair`** - PAR2-based recovery with metadata parameter restoration
- **`cpack info`** - Professional tree-structured metadata display
- **`cpack list`** - Advanced file listing with filtering and pagination

### 🛡️ Advanced Verification & Recovery
- **4-Layer Verification System**: 7z integrity → SHA-256 → BLAKE3 → PAR2
- **Dual Cryptographic Hashing**: SHA-256 + BLAKE3 for comprehensive integrity
- **PAR2 Recovery Files**: 10% redundancy with multi-core generation
- **Parameter Persistence**: Complete metadata.toml with automatic parameter recovery

### 🌐 Cross-Platform Excellence
- **Universal Compatibility**: Windows, macOS, Linux with full Unicode support
- **Intelligent System File Filtering**: Auto-exclusion of .DS_Store, Thumbs.db, etc.
- **Windows Filename Handling**: Automatic conflict resolution and sanitization
- **Professional Logging**: Structured output with comprehensive progress tracking

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

> **📋 Detailed Setup**: For comprehensive installation instructions including development setup, see [Installation Guide](docs/INSTALLATION.md)

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

### Professional Features

```bash
# Custom compression levels (0-9)
cpack create large-dataset/ --level 9 --dict 512m --output-dir ~/archives

# Pre-verification before extraction
cpack extract suspicious-archive.7z --verify --output-dir ~/safe-extraction

# Repair corrupted files using PAR2
cpack repair ~/cold-storage/damaged-archive.7z

# Professional metadata display
cpack info ~/cold-storage/documents.7z
```

> **📚 Complete Examples**: See [Usage Examples](docs/EXAMPLES.md) for comprehensive use cases and advanced workflows.

## Technical Specifications

### Supported Input Formats
- **Directories**: Any filesystem directory structure
- **Archive Formats**: 7z, zip, rar, tar, tar.gz, tar.bz2, tar.xz, tar.zst

### Professional 7z Output Structure
```
archive-name/
├── archive-name.7z              # Main 7z archive
├── archive-name.7z.sha256       # SHA-256 hash
├── archive-name.7z.blake3       # BLAKE3 hash
├── archive-name.7z.par2         # PAR2 recovery files
└── metadata/
    └── metadata.toml            # Complete archive metadata
```

### 4-Layer Verification System

1. **🏗️ 7z Integrity**: Native 7z archive structure validation
2. **🔐 SHA-256**: Cryptographic hash verification (legacy compatibility)
3. **⚡ BLAKE3**: Modern high-performance cryptographic hash
4. **🛡️ PAR2 Recovery**: Error correction with 10% redundancy

### 7-Tier Dynamic Compression

| File Size Range | Compression Level | Dictionary Size | Use Case |
|-----------------|-------------------|-----------------|----------|
| < 256 KiB | Level 1 | 128k | Minimal resources |
| 256 KiB – 1 MiB | Level 3 | 1m | Light compression |
| 1 – 8 MiB | Level 5 | 4m | Balanced performance |
| 8 – 64 MiB | Level 6 | 16m | Good compression |
| 64 – 512 MiB | Level 7 | 64m | High compression |
| 512 MiB – 2 GiB | Level 9 | 256m | Maximum compression |
| > 2 GiB | Level 9 | 512m | Ultimate compression |

> **🔧 Technical Details**: For architecture documentation and advanced configuration, see [Architecture Guide](docs/ARCHITECTURE.md)

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

**Development Standards**: 134 comprehensive tests, ruff formatting, MyPy type checking, cross-platform CI/CD

> **🔨 Developer Guide**: Comprehensive development instructions in [CLAUDE.md](CLAUDE.md)

## License & Support

**License**: MIT - See [LICENSE](LICENSE) for details

**Documentation**:
- 📖 [Installation Guide](docs/INSTALLATION.md) - Comprehensive setup instructions
- 📋 [CLI Reference](docs/CLI_REFERENCE.md) - Complete command documentation
- 💡 [Usage Examples](docs/EXAMPLES.md) - Real-world use cases and workflows
- 🏗️ [Architecture Guide](docs/ARCHITECTURE.md) - Technical implementation details

**Support**: [GitHub Issues](https://github.com/rxchi1d/coldpack/issues) | [Discussions](https://github.com/rxchi1d/coldpack/discussions)

---

<div align="center">

**coldpack v0.1.0** - *Professional 7z Cold Storage Solution*

*Engineered for reliability, optimized for performance, designed for the future.*

</div>
