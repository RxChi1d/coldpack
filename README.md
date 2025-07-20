# coldpack

Cross-platform cold storage CLI package for standardized tar.zst archives with comprehensive verification.

## Overview

coldpack is a Python CLI package designed for creating standardized cold storage archives. It converts various archive formats (7z, zip, rar, tar.gz, etc.) into a unified tar.zst format with comprehensive verification and recovery mechanisms.

## Features

- **Multi-format Support**: Extract from 11+ archive formats including 7z, zip, rar, tar.gz, tar.bz2, tar.xz
- **Standardized Output**: Unified tar.zst format for long-term storage
- **5-Layer Verification**: TAR header, Zstd integrity, SHA-256, BLAKE3, PAR2 recovery
- **Cross-platform**: Works on Linux, macOS, and Windows
- **High Performance**: Uses par2cmdline-turbo for fast PAR2 operations
- **Rich CLI**: Beautiful progress displays and detailed output

## Installation

### Using uv (Recommended)

```bash
uv add coldpack
```

### Using pip

```bash
pip install coldpack
```

## Requirements

- Python 3.9+
- External tools (automatically installed via PyPI packages):
  - `par2cmdline-turbo` for PAR2 operations
  - System `tar` command

## Quick Start

### Create a Cold Storage Archive

```bash
# Archive a directory
cpack archive /path/to/source --output-dir /path/to/output

# Archive an existing archive file
cpack archive archive.zip --output-dir /path/to/output

# Custom compression level
cpack archive /path/to/source --compression-level 22 --ultra
```

### Extract an Archive

```bash
# Extract cold storage archive
cpack extract archive.tar.zst --output-dir /path/to/extract

# Extract any supported format
cpack extract archive.7z --output-dir /path/to/extract
```

### Verify Archive Integrity

```bash
# Full 5-layer verification
cpack verify archive.tar.zst

# Quick verification (TAR + Zstd only)
cpack verify archive.tar.zst --quick
```

### Repair Corrupted Archive

```bash
# Repair using PAR2 recovery files
cpack repair archive.tar.zst
```

### Archive Information

```bash
# Display archive metadata
cpack info archive.tar.zst

# List supported formats
cpack formats
```

## Supported Formats

### Input Formats (11 supported)
- `.7z` - 7-Zip archives
- `.zip` - ZIP archives  
- `.rar` - RAR archives
- `.tar` - TAR archives
- `.tar.gz`, `.tgz` - Gzip compressed TAR
- `.tar.bz2`, `.tbz2` - Bzip2 compressed TAR
- `.tar.xz`, `.txz` - XZ compressed TAR
- `.tar.zst` - Zstandard compressed TAR

### Output Format
- `.tar.zst` - TAR archive compressed with Zstandard

## Verification Layers

coldpack implements a comprehensive 5-layer verification system:

1. **TAR Header**: Validates TAR archive structure and metadata
2. **Zstd Integrity**: Verifies Zstandard compression integrity
3. **SHA-256**: Cryptographic hash verification (legacy compatibility)
4. **BLAKE3**: Modern cryptographic hash verification
5. **PAR2 Recovery**: Error correction and recovery capability

## Configuration

### Compression Settings

```python
from coldpack import CompressionSettings

# High compression (default)
settings = CompressionSettings(
    level=19,           # Compression level (1-22)
    ultra_mode=False,   # Enable ultra mode (levels 20-22)
    threads=0,          # Auto-detect CPU cores
    long_mode=True      # Enable long-distance matching
)

# Maximum compression
settings = CompressionSettings(
    level=22,
    ultra_mode=True,
    threads=0
)
```

### Processing Options

```python
from coldpack import ProcessingOptions

options = ProcessingOptions(
    verify_integrity=True,    # Enable verification
    generate_par2=True,       # Generate PAR2 files
    par2_redundancy=10,       # 10% redundancy
    cleanup_on_error=True,    # Clean up on failure
    verbose=True              # Detailed output
)
```

## API Usage

```python
from coldpack import ColdStorageArchiver
from pathlib import Path

# Create archiver
archiver = ColdStorageArchiver()

# Create archive
result = archiver.create_archive(
    source=Path("/path/to/source"),
    output_dir=Path("/path/to/output"),
    archive_name="my_archive"
)

if result.success:
    print(f"Archive created: {result.archive_path}")
    print(f"Original size: {result.metadata.original_size}")
    print(f"Compressed size: {result.metadata.compressed_size}")
    print(f"Compression ratio: {result.metadata.compression_percentage:.1f}%")
else:
    print(f"Archive failed: {result.error}")
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd coldpack

# Install with uv
uv sync --dev

# Activate environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

### Development Commands

```bash
# Code formatting
uv run ruff format .

# Linting
uv run ruff check --fix .

# Type checking
uv run mypy src/

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/coldpack --cov-report=html
```

### Project Structure

```
coldpack/
├── src/coldpack/
│   ├── __init__.py          # Main API exports
│   ├── cli.py               # CLI interface
│   ├── config/              # Configuration management
│   ├── core/                # Core business logic
│   │   ├── archiver.py      # Main archiving engine
│   │   ├── extractor.py     # Multi-format extraction
│   │   ├── verifier.py      # 5-layer verification
│   │   └── repairer.py      # PAR2 repair functionality
│   └── utils/               # Utility modules
│       ├── compression.py   # Zstd compression
│       ├── hashing.py       # Dual hash system
│       ├── par2.py          # PAR2 operations
│       ├── filesystem.py    # File operations
│       └── progress.py      # Progress tracking
├── tests/                   # Test suite
├── docs/                    # Documentation
└── examples/                # Usage examples
```

## Performance Considerations

- **Large Files**: Uses streaming processing to handle files of any size
- **Memory Usage**: Optimized for minimal memory footprint
- **CPU Utilization**: Automatic multi-threading for compression
- **Disk Space**: Requires ~2x source size for temporary operations

## Security Features

- **Cryptographic Hashing**: Dual hash system (SHA-256 + BLAKE3)
- **Data Integrity**: Multiple verification layers
- **Safe Operations**: Secure temporary file handling
- **Error Recovery**: PAR2-based corruption repair

## Roadmap

- [ ] GUI interface
- [ ] Cloud storage integration
- [ ] Incremental backups
- [ ] Archive encryption
- [ ] Metadata database
- [ ] Network synchronization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the development guidelines
4. Add tests for new functionality
5. Submit a pull request

## License

BSD-3-Clause License. See [LICENSE](LICENSE) for details.

## Support

- Documentation: [CLI Reference](docs/CLI_REFERENCE.md)
- Examples: [Usage Examples](docs/EXAMPLES.md) 
- Issues: [GitHub Issues](https://github.com/rxchi1d/coldpack/issues)

---

**coldpack** - Reliable, standardized cold storage for your important data.