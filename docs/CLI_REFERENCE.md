# CLI Reference

Complete command-line interface reference for coldpack.

## Overview

The `cpack` command provides a comprehensive CLI for cold storage archive operations. All commands support common options and provide rich, interactive output.

## Global Options

```bash
cpack --help                    # Show help message
cpack --version                # Show version information
```

## Commands

### `cpack archive`

Create a cold storage archive from a source directory or file.

#### Syntax
```bash
cpack archive [OPTIONS] SOURCE
```

#### Arguments
- `SOURCE` - Source directory or archive file to process

#### Options
```bash
--output-dir, -o DIRECTORY      # Output directory (default: ./archives)
--archive-name, -n NAME         # Custom archive name (default: source name)
--compression-level, -l LEVEL   # Compression level 1-22 (default: 19)
--threads, -t COUNT             # Number of threads (default: auto)
--ultra                         # Enable ultra compression mode (levels 20-22)
--no-verify                     # Skip integrity verification
--no-par2                       # Skip PAR2 recovery file generation
--par2-redundancy PERCENT       # PAR2 redundancy percentage (default: 10)
--force                         # Overwrite existing archives
--verbose, -v                   # Verbose output
--quiet, -q                     # Minimal output
```

#### Examples
```bash
# Basic archive creation
cpack archive /path/to/source

# Custom output directory and name
cpack archive /path/to/source -o /backup -n important_data

# Maximum compression
cpack archive /path/to/source -l 22 --ultra

# Fast compression with more threads
cpack archive /path/to/source -l 12 -t 8

# Skip verification for speed
cpack archive /path/to/source --no-verify --no-par2

# Archive an existing 7z file
cpack archive archive.7z -o /backup
```

#### Output Files
```
output_directory/
└── archive_name/
    ├── archive_name.tar.zst              # Main archive
    ├── archive_name.tar.zst.sha256       # SHA-256 hash
    ├── archive_name.tar.zst.blake3       # BLAKE3 hash
    ├── archive_name.tar.zst.par2         # PAR2 index
    └── archive_name.tar.zst.vol*.par2    # PAR2 recovery files
```

### `cpack extract`

Extract a cold storage archive or any supported archive format.

#### Syntax
```bash
cpack extract [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - Archive file to extract

#### Options
```bash
--output-dir, -o DIRECTORY      # Output directory (default: ./extracted)
--verify                        # Verify before extraction (for .tar.zst)
--force                         # Overwrite existing files
--preserve-structure            # Preserve original directory structure
--verbose, -v                   # Verbose output
--quiet, -q                     # Minimal output
```

#### Examples
```bash
# Basic extraction
cpack extract archive.tar.zst

# Extract to specific directory
cpack extract archive.tar.zst -o /tmp/restore

# Extract with verification
cpack extract archive.tar.zst --verify

# Extract any supported format
cpack extract archive.7z -o /tmp/extract

# Force overwrite existing files
cpack extract archive.tar.zst --force
```

### `cpack verify`

Verify archive integrity using multiple verification layers.

#### Syntax
```bash
cpack verify [OPTIONS] ARCHIVE [ARCHIVE...]
```

#### Arguments
- `ARCHIVE` - One or more archive files to verify

#### Options
```bash
--quick                         # Quick verification (TAR + Zstd only)
--full                          # Full 5-layer verification (default)
--repair                        # Attempt repair if verification fails
--verbose, -v                   # Detailed verification output
--quiet, -q                     # Only show results
```

#### Verification Layers
1. **TAR Header** - Archive structure validation
2. **Zstd Integrity** - Compression integrity check
3. **SHA-256 Hash** - Legacy hash verification
4. **BLAKE3 Hash** - Modern hash verification
5. **PAR2 Recovery** - Error correction validation

#### Examples
```bash
# Full verification
cpack verify archive.tar.zst

# Quick verification
cpack verify archive.tar.zst --quick

# Verify multiple archives
cpack verify *.tar.zst

# Verify with auto-repair
cpack verify archive.tar.zst --repair

# Batch verification (quiet)
cpack verify /backup/*.tar.zst --quiet
```

#### Exit Codes
- `0` - All verifications passed
- `5` - Verification failed
- `1` - General error

### `cpack repair`

Repair a corrupted archive using PAR2 recovery files.

#### Syntax
```bash
cpack repair [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - Archive file to repair (must have .par2 files)

#### Options
```bash
--verify-after                  # Verify archive after repair
--backup                        # Create backup before repair
--force                         # Force repair even if verification passes
--verbose, -v                   # Detailed repair output
--quiet, -q                     # Minimal output
```

#### Examples
```bash
# Repair corrupted archive
cpack repair archive.tar.zst

# Repair with post-verification
cpack repair archive.tar.zst --verify-after

# Repair with backup
cpack repair archive.tar.zst --backup

# Force repair
cpack repair archive.tar.zst --force
```

#### Requirements
- Archive must have corresponding `.par2` files
- PAR2 files must be in the same directory
- Sufficient PAR2 redundancy to repair damage

### `cpack info`

Display detailed information about an archive.

#### Syntax
```bash
cpack info [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - Archive file to analyze

#### Options
```bash
--format json                   # Output in JSON format
--format table                  # Output in table format (default)
--show-hashes                   # Display hash values
--show-par2                     # Display PAR2 information
--verbose, -v                   # Extended information
```

#### Examples
```bash
# Basic information
cpack info archive.tar.zst

# JSON output
cpack info archive.tar.zst --format json

# Extended information
cpack info archive.tar.zst --verbose --show-hashes

# PAR2 status
cpack info archive.tar.zst --show-par2
```

#### Information Displayed
- Archive size and compression ratio
- Creation date and metadata
- Verification status
- Hash values (if requested)
- PAR2 recovery information
- File count and structure

### `cpack formats`

List all supported archive formats.

#### Syntax
```bash
cpack formats [OPTIONS]
```

#### Options
```bash
--input                         # Show only input formats
--output                        # Show only output formats
--verbose, -v                   # Show format descriptions
```

#### Examples
```bash
# List all formats
cpack formats

# Input formats only
cpack formats --input

# Detailed format information
cpack formats --verbose
```

## Configuration Files

### Global Configuration
```bash
~/.config/coldpack/config.toml
```

### Project Configuration
```bash
./coldpack.toml
```

### Configuration Example
```toml
[compression]
level = 19
ultra_mode = false
threads = 0
long_mode = true

[processing]
verify_integrity = true
generate_par2 = true
par2_redundancy = 10
cleanup_on_error = true

[output]
default_directory = "./archives"
organize_by_date = false
preserve_structure = true
```

## Environment Variables

```bash
COLDPACK_CONFIG_DIR=/path/to/config    # Config directory
COLDPACK_TEMP_DIR=/path/to/temp        # Temporary files directory
COLDPACK_DEFAULT_OUTPUT=/path/to/out   # Default output directory
COLDPACK_COMPRESSION_LEVEL=19          # Default compression level
COLDPACK_THREADS=8                     # Default thread count
COLDPACK_VERBOSE=1                     # Enable verbose output
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | File not found |
| 3 | Permission error |
| 4 | Insufficient disk space |
| 5 | Verification failed |
| 6 | Required tool not found |
| 7 | Invalid format |
| 8 | Compression failed |
| 9 | Extraction failed |

## Performance Tips

### Large Files
```bash
# Use more threads for large files
cpack archive large_dataset/ -t 16

# Reduce memory usage for very large files
cpack archive large_dataset/ -l 12
```

### Batch Operations
```bash
# Process multiple archives efficiently
for archive in *.7z; do
    cpack archive "$archive" --quiet
done

# Parallel processing
find . -name "*.7z" | xargs -P 4 -I {} cpack archive {}
```

### Storage Optimization
```bash
# Maximum compression for archival
cpack archive important_data/ -l 22 --ultra

# Balanced compression for regular use
cpack archive data/ -l 15 -t 8

# Fast compression for temporary archives
cpack archive temp_data/ -l 3 --no-par2
```

## Integration Examples

### Backup Scripts
```bash
#!/bin/bash
# Daily backup script
DATE=$(date +%Y%m%d)
cpack archive /important/data -o /backup -n "backup_$DATE"
```

### Verification Cron Job
```bash
# Add to crontab for weekly verification
0 2 * * 0 /usr/local/bin/cpack verify /backup/*.tar.zst --quiet
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Create Archive
  run: |
    cpack archive ./build/artifacts --output ./archives
    cpack verify ./archives/*.tar.zst
```

## Troubleshooting

### Common Issues

**Command not found**
```bash
# Ensure coldpack is installed
pip show coldpack
# or
uv list | grep coldpack
```

**Permission denied**
```bash
# Check file permissions
ls -la archive.tar.zst
# Fix permissions
chmod 644 archive.tar.zst
```

**Insufficient space**
```bash
# Check available space
df -h
# Use different temporary directory
COLDPACK_TEMP_DIR=/large/partition cpack archive data/
```

**PAR2 tool not found**
```bash
# Check PAR2 installation
which par2
# Should be automatically available via par2cmdline-turbo package
```

### Debug Mode
```bash
# Enable debug logging
COLDPACK_VERBOSE=1 cpack archive data/ -v
```

### Getting Help
```bash
# Command-specific help
cpack archive --help
cpack verify --help

# General help
cpack --help
```

---

For more examples and advanced usage, see [EXAMPLES.md](EXAMPLES.md).
