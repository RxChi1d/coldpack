# Changelog

All notable changes to the coldpack project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- GUI interface for non-technical users
- Cloud storage integration (S3, Azure, GCP)
- Incremental backup support
- Archive encryption capabilities
- Metadata database for archive management
- Network synchronization features

## [0.1.0] - 2024-07-19

### Added

#### Core Features
- **Multi-format Archive Support**: Extract from 11+ archive formats (7z, zip, rar, tar.gz, etc.)
- **Standardized Output**: Unified tar.zst format for long-term cold storage
- **5-Layer Verification System**:
  - TAR header validation
  - Zstd compression integrity
  - SHA-256 hash verification (legacy compatibility)
  - BLAKE3 hash verification (modern cryptographic hash)
  - PAR2 error correction and recovery
- **Cross-platform Compatibility**: Windows, macOS, and Linux support

#### CLI Interface (`cpack` command)
- `cpack archive` - Create cold storage archives with comprehensive verification
- `cpack extract` - Extract archives with format auto-detection
- `cpack verify` - Multi-layer integrity verification
- `cpack repair` - PAR2-based corruption repair
- `cpack info` - Archive metadata and status information
- `cpack formats` - List supported input/output formats

#### Core Components
- **ColdStorageArchiver**: Main archiving engine with 10-step processing pipeline
- **MultiFormatExtractor**: py7zz-based extraction supporting 50+ formats
- **ArchiveVerifier**: Comprehensive verification with detailed reporting
- **ArchiveRepairer**: PAR2-based repair with integrity validation

#### Utility Systems
- **ZstdCompressor/Decompressor**: High-performance compression with dynamic parameters
- **DualHasher**: Parallel SHA-256 + BLAKE3 computation
- **PAR2Manager**: Cross-platform PAR2 operations
- **ProgressTracker**: Rich-based progress display with multi-task support
- **Filesystem Utils**: Safe temporary file management and disk space monitoring

#### Configuration Management
- **Pydantic Models**: Type-safe configuration with validation
- **CompressionSettings**: Customizable compression parameters (levels 1-22, ultra mode)
- **ArchiveMetadata**: Comprehensive archive information tracking
- **ProcessingOptions**: Runtime behavior control

#### Dependencies and Performance
- **par2cmdline-turbo**: High-performance PAR2 operations via PyPI
- **py7zz**: Multi-format extraction library
- **zstandard**: Modern compression with excellent ratio and speed
- **blake3**: Fast cryptographic hashing
- **typer**: Modern CLI framework with rich help
- **rich**: Beautiful terminal output and progress tracking
- **pydantic**: Data validation and settings management
- **loguru**: Structured logging

### Technical Specifications

#### Supported Input Formats
- 7-Zip (`.7z`)
- ZIP archives (`.zip`)
- RAR archives (`.rar`)
- TAR archives (`.tar`)
- Gzip compressed TAR (`.tar.gz`, `.tgz`)
- Bzip2 compressed TAR (`.tar.bz2`, `.tbz2`)
- XZ compressed TAR (`.tar.xz`, `.txz`)
- Zstandard compressed TAR (`.tar.zst`)

#### Output Format
- TAR archive compressed with Zstandard (`.tar.zst`)
- Accompanied by verification files:
  - `.sha256` - SHA-256 hash
  - `.blake3` - BLAKE3 hash
  - `.par2` - PAR2 index and recovery files

#### System Requirements
- Python 3.9+ (support for Python 3.8 removed for compatibility)
- Cross-platform: Linux, macOS, Windows
- External dependencies automatically installed via PyPI
- Minimum 1GB free disk space for processing
- Recommended: SSD for temporary operations

#### Performance Characteristics
- **Compression**: Zstd levels 1-22 with ultra mode support
- **Threading**: Automatic CPU core detection with manual override
- **Memory**: Optimized for minimal footprint with streaming processing
- **Verification**: Parallel hash computation for speed
- **Recovery**: 10% PAR2 redundancy (configurable)

### Development Infrastructure

#### Code Quality
- **Ruff**: Code formatting and linting (line-length=88)
- **MyPy**: Complete static type checking with strict mode
- **Pytest**: Comprehensive test suite with 27 test cases
- **Coverage**: HTML and terminal coverage reporting

#### Supported Python Versions
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

#### Project Structure
```
coldpack/
├── src/coldpack/           # Source code
│   ├── cli.py             # CLI interface
│   ├── config/            # Configuration management
│   ├── core/              # Core business logic
│   └── utils/             # Utility modules
├── tests/                 # Test suite
├── docs/                  # Documentation
└── examples/              # Usage examples
```

#### Documentation
- **README.md**: Project overview and quick start
- **CLI_REFERENCE.md**: Complete command-line interface documentation
- **EXAMPLES.md**: Comprehensive usage examples and integration patterns
- **CHANGELOG.md**: Version history and changes

### Configuration Files
- **pyproject.toml**: Project configuration with full dependency specification
- **CLAUDE.md**: Development guidelines and project standards

### Version Strategy
- Follows [Semantic Versioning](https://semver.org/)
- Git-based versioning with `hatch-vcs`
- Automated version detection from Git tags

---

## Version History Legend

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Now removed features
- **Fixed**: Any bug fixes
- **Security**: In case of vulnerabilities

---

**Note**: This is the initial release of coldpack as a Python package. Previous versions existed as shell scripts but have been completely rewritten for this Python implementation.
