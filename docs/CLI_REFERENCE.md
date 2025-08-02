# CLI Reference

Complete command-line interface reference for coldpack v0.2.0a1.

## Overview

The `cpack` command provides a CLI for 7z cold storage operations with dynamic compression and verification systems.

## Global Options

```bash
cpack --help                    # Show help message
cpack --version                # Show version information
```

## Commands

### `cpack create`

Create a 7z cold storage archive with verification and recovery systems.

#### Syntax
```bash
cpack create [OPTIONS] SOURCE
```

#### Arguments
- `SOURCE` - Source directory or any supported archive format (7z, zip, rar, tar.gz, etc.)

#### Compression Options
```bash
--level, -l LEVEL               # Compression level 0-9 (default: dynamic)
--dict, -d SIZE                 # Dictionary size: 128k-512m (default: dynamic)
--threads, -t COUNT             # Thread count (default: 0 = all cores)
--output-dir, -o DIRECTORY      # Output directory (default: current)
--name, -n NAME                 # Archive name (default: source name)
```

#### Verification Options
```bash
--no-verify-7z                  # Skip 7z integrity verification
--no-verify-sha256              # Skip SHA256 hash verification
--no-verify-blake3              # Skip BLAKE3 hash verification
--no-verify-par2                # Skip PAR2 recovery verification
--par2-redundancy PERCENT       # PAR2 redundancy (default: 10%)
```

#### General Options
```bash
--force                         # Overwrite existing archives
--verbose, -v                   # Detailed progress output
--quiet, -q                     # Minimal output
```

#### Dynamic Compression Tiers

| File Size | Level | Dict Size | Use Case |
|-----------|-------|-----------|----------|
| < 256 KiB | 1 | 128k | Minimal resources |
| 256K-1M | 3 | 1m | Light compression |
| 1-8M | 5 | 4m | Balanced performance |
| 8-64M | 6 | 16m | Good compression |
| 64-512M | 7 | 64m | High compression |
| 512M-2G | 9 | 256m | Maximum compression |
| > 2 GiB | 9 | 512m | Ultimate compression |

#### Examples
```bash
# Basic 7z cold storage creation (dynamic optimization)
cpack create /path/to/documents

# Custom output location and name
cpack create /path/to/source --output-dir /backup --name critical-data

# Maximum compression for archival storage
cpack create large-dataset/ --level 9 --dict 512m

# Fast compression for temporary archives
cpack create temp-files/ --level 3 --dict 1m

# Multi-format input processing
cpack create existing-archive.zip --output-dir /cold-storage
cpack create backup.tar.gz --name converted-backup

# Verification customization
cpack create sensitive-data/ --par2-redundancy 20  # 20% PAR2 redundancy
cpack create fast-data/ --no-verify-par2           # Skip PAR2 for speed
```

#### 7z Output Structure
```
output_directory/
└── archive_name/
    ├── archive_name.7z              # Main 7z archive
    ├── archive_name.7z.sha256       # SHA-256 hash file
    ├── archive_name.7z.blake3       # BLAKE3 hash file
    ├── archive_name.7z.par2         # PAR2 index file
    ├── archive_name.7z.vol*.par2    # PAR2 recovery files
    └── metadata/
        └── metadata.toml            # Complete archive metadata
```

### `cpack extract`

Extract archives with automatic parameter recovery and optional pre-verification.

#### Syntax
```bash
cpack extract [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - Archive file to extract (7z, zip, rar, tar.gz, etc.)

#### Options
```bash
--output-dir, -o DIRECTORY      # Output directory (default: current/extracted)
--verify                        # Pre-extraction integrity verification
--force                         # Overwrite existing files
--verbose, -v                   # Detailed extraction progress
--quiet, -q                     # Minimal output
```

#### Automatic Parameter Recovery
For coldpack 7z archives, extraction automatically uses original compression parameters from `metadata/metadata.toml`:
- Original compression level and dictionary size
- Thread count and method settings
- Intelligent fallback for missing metadata

#### Examples
```bash
# Basic extraction with automatic parameter recovery
cpack extract backup.7z

# Extract to specific directory
cpack extract documents.7z --output-dir /tmp/restore

# Pre-verification before extraction (recommended for critical data)
cpack extract critical-archive.7z --verify --output-dir /safe-location

# Extract legacy formats
cpack extract old-backup.zip --output-dir /converted
cpack extract data.tar.gz --output-dir /extracted

# Force overwrite with verbose progress
cpack extract archive.7z --force --verbose --output-dir /overwrite-location
```

#### Extraction Process
1. **Format Detection**: Automatic identification of archive format
2. **Metadata Loading**: Recovery of original parameters (for coldpack archives)
3. **Pre-Verification**: Optional 4-layer integrity check
4. **Smart Extraction**: Optimized extraction with parameter recovery
5. **Progress Tracking**: Real-time extraction progress display

### `cpack verify`

Comprehensive 4-layer integrity verification with auto-discovery of related files.

#### Syntax
```bash
cpack verify [OPTIONS] ARCHIVE [ARCHIVE...]
```

#### Arguments
- `ARCHIVE` - One or more 7z archive files to verify

#### Options
```bash
--verbose, -v                   # Detailed verification progress
--quiet, -q                     # Results only (suitable for scripts)
```

#### 4-Layer Verification System
1. **🏗️ 7z Integrity**: Native 7z archive structure validation
2. **🔐 SHA-256**: Cryptographic hash verification (legacy compatibility)
3. **⚡ BLAKE3**: Modern high-performance cryptographic hash
4. **🛡️ PAR2 Recovery**: Error correction validation with automatic file discovery

#### Auto-Discovery Features
- Automatic detection of `.sha256`, `.blake3`, and `.par2` files
- Intelligent metadata location detection (`metadata/metadata.toml`)
- Cross-directory PAR2 file handling
- Smart working directory management

#### Examples
```bash
# Complete 4-layer verification (with auto-discovery)
cpack verify documents.7z

# Batch verification with progress
cpack verify /backup/*.7z --verbose

# Script-friendly quiet verification
cpack verify critical-data.7z --quiet
echo $?  # Check exit code: 0 = success, 5 = failed

# Verify multiple archives
cpack verify archive1.7z archive2.7z archive3.7z

# Directory-based verification
find /backup -name "*.7z" -exec cpack verify {} \;
```

#### Verification Output
```
Starting 4-layer verification for: documents.7z
✓ 7z integrity check passed
✓ SHA256 hash verification passed
✓ BLAKE3 hash verification passed
✓ PAR2 integrity check passed
SUCCESS: Verification complete: all 4 layers passed
```

#### Exit Codes
- `0` - All verification layers passed
- `5` - One or more verification layers failed
- `1` - General error (file not found, permission denied, etc.)

### `cpack repair`

PAR2-based file recovery with metadata parameter restoration.

#### Syntax
```bash
cpack repair [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - 7z archive file to repair (requires PAR2 recovery files)

#### Options
```bash
--verify-after                  # Verify archive integrity after repair
--verbose, -v                   # Detailed repair progress
--quiet, -q                     # Minimal output
```

#### Automatic Parameter Recovery
The repair process automatically restores original compression parameters from `metadata/metadata.toml` for optimal recovery performance.

#### Examples
```bash
# Basic PAR2 repair
cpack repair corrupted-archive.7z

# Repair with post-verification (recommended)
cpack repair important-data.7z --verify-after

# Quiet repair for batch processing
cpack repair damaged.7z --quiet
```

#### Repair Process
1. **Parameter Recovery**: Load original settings from metadata.toml
2. **PAR2 Analysis**: Assess damage and recovery requirements
3. **Multi-Core Repair**: Utilize all available CPU cores for recovery
4. **Integrity Verification**: Optional post-repair 4-layer verification

#### Requirements
- Corresponding `.par2` and `.vol*.par2` files must be present
- Sufficient PAR2 redundancy to repair the level of damage
- PAR2 files can be in same directory or `metadata/` subdirectory

### `cpack info`

Tree-structured archive metadata display.

#### Syntax
```bash
cpack info [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - 7z archive file to analyze

#### Options
```bash
--verbose, -v                   # Extended metadata information
--quiet, -q                     # Minimal output format
```

#### Tree Display
The info command presents archive metadata in five organized sections:
- **Basic Information**: Path, format, size, compression ratio
- **Content Summary**: File count, directory count, total size (tree structure)
- **Creation Settings**: Compression level, dictionary size, threads, method
- **Integrity Status**: SHA-256, BLAKE3, PAR2 status with check marks
- **Metadata Information**: Creation time, coldpack version, related files

#### Examples
```bash
# Archive metadata display
cpack info documents.7z

# Extended information with verbose details
cpack info backup.7z --verbose

# Minimal output for scripting
cpack info archive.7z --quiet
```

#### Sample Output
```
Archive: documents.7z
Path: /backup/documents.7z
Format: 7z archive
Size: 2.56 MB (15.2 MB → 2.56 MB, 83.2% compression)

Content Summary:
├── Files: 127
├── Directories: 18
├── Total Size: 15.2 MB
└── Compression: 83.2%

Creation Settings:
├── Compression Level: 7
├── Dictionary Size: 64m
├── Threads: all
└── Method: LZMA2

Integrity:
├── SHA-256: a1b2c3d4e5f6... ✓
├── BLAKE3:  x1y2z3w4v5u6... ✓
└── PAR2:    10% redundancy, 3 recovery files ✓

Metadata:
├── Created: 2025-07-26 10:30:15 UTC
├── coldpack: v0.1.0
└── Related Files: documents.7z.sha256, documents.7z.blake3, documents.7z.par2
```

#### Performance Optimization
- Optimized for large archives (no file enumeration)
- Fast metadata-only analysis
- Tree-structured Rich output formatting

### `cpack list`

File listing with filtering, pagination, and search capabilities.

#### Syntax
```bash
cpack list [OPTIONS] ARCHIVE
```

#### Arguments
- `ARCHIVE` - Archive file to list (supports all input formats)

#### Display Options
```bash
--limit, -l COUNT               # Limit number of entries displayed
--offset, -o COUNT              # Skip first N entries (pagination)
--filter, -f PATTERN            # Filter files with glob pattern
--dirs-only                     # Show only directories
--files-only                    # Show only files
--summary-only                  # Show summary statistics only
```

#### Output Options
```bash
--verbose, -v                   # Include detailed file information
--quiet, -q                     # Minimal output format
```

#### Examples
```bash
# Basic file listing
cpack list documents.7z

# Pagination for large archives
cpack list large-archive.7z --limit 50 --offset 100

# Filter specific file types
cpack list photos.7z --filter "*.jpg" --filter "*.png"
cpack list documents.7z --filter "*.pdf"

# Directory structure only
cpack list backup.7z --dirs-only

# Files only (no directories)
cpack list archive.7z --files-only

# Quick summary for large archives
cpack list massive-dataset.7z --summary-only

# Detailed listing with file metadata
cpack list documents.7z --verbose

# Script-friendly minimal output
find /backup -name "*.7z" -exec cpack list {} --files-only --quiet \;
```

#### Sample Output
```
Archive: documents.7z (127 files, 18 directories)

Path                          Size      Date         Type
────────────────────────────────────────────────────────
documents/                    -         2025-07-26   DIR
documents/README.md           2.1 KB    2025-07-26   FILE
documents/reports/            -         2025-07-25   DIR
documents/reports/annual.pdf  847 KB    2025-07-25   FILE
documents/images/             -         2025-07-24   DIR
documents/images/chart.png    156 KB    2025-07-24   FILE
...

Showing 1-20 of 127 entries. Use --limit and --offset for more.
Total: 127 files, 18 directories (15.2 MB)
```

#### Performance Features
- **Cross-Platform Directory Detection**: Robust identification on Windows, macOS, Linux
- **Large Archive Optimization**: Intelligent handling of archives with thousands of files
- **Unicode Path Support**: Full support for international filenames
- **Real-Time Filtering**: Fast glob pattern matching during listing

### `cpack formats`

Display supported input archive formats.

#### Syntax
```bash
cpack formats [OPTIONS]
```

#### Options
```bash
--verbose, -v                   # Show format descriptions and capabilities
```

#### Examples
```bash
# List supported formats
cpack formats

# Detailed format information
cpack formats --verbose
```

#### Supported Input Formats
- **Directories**: Any filesystem directory structure
- **7z Archives**: .7z files (7-Zip format)
- **ZIP Archives**: .zip files
- **RAR Archives**: .rar files
- **TAR Archives**: .tar, .tar.gz, .tar.bz2, .tar.xz, .tar.zst

#### Output Format
- **7z Cold Storage**: 7z archives with verification

## Configuration

coldpack supports configuration through environment variables and configuration files.

### Key Environment Variables
```bash
COLDPACK_DEFAULT_OUTPUT=/backup        # Default output directory
COLDPACK_COMPRESSION_LEVEL=7           # Default compression level (0-9)
COLDPACK_THREADS=0                     # Thread count (0 = all cores)
```

### Configuration Files
- **Global**: `~/.config/coldpack/config.toml`
- **Project**: `./coldpack.toml`

For comprehensive configuration options, see [Architecture Guide](ARCHITECTURE.md).

## Exit Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 0 | Success | All operations completed successfully |
| 1 | General error | Command-line syntax or runtime errors |
| 2 | File not found | Archive or source file doesn't exist |
| 3 | Permission error | Insufficient permissions for file operations |
| 4 | Insufficient space | Not enough disk space for operation |
| 5 | Verification failed | Integrity check failed in verify command |
| 6 | Tool not found | Required external tool unavailable |

## Usage Patterns

### Production Archival
```bash
# Maximum compression for long-term storage
cpack create critical-data/ --level 9 --dict 512m --output-dir /archive

# Backup with high PAR2 redundancy
cpack create database-backup/ --par2-redundancy 15 --output-dir /backup
```

### Development Workflows
```bash
# Fast compression for CI/CD
cpack create build-artifacts/ --level 3 --dict 4m --no-verify-par2

# Verification in automated testing
cpack verify /backup/*.7z --quiet && echo "All backups verified"
```

### Batch Processing
```bash
# Process multiple directories efficiently
find /data -maxdepth 1 -type d -exec cpack create {} --output-dir /cold-storage \;

# Parallel archive creation
ls /source/ | xargs -P 4 -I {} cpack create /source/{} --output-dir /archives
```

## Automation & Integration

### Backup Scripts
```bash
#!/bin/bash
# Daily backup with verification
DATE=$(date +%Y%m%d)
BACKUP_NAME="backup_$DATE"

# Create archive with maximum compression
cpack create /critical/data --output-dir /backup --name "$BACKUP_NAME" --level 9

# Verify integrity
cpack verify "/backup/$BACKUP_NAME.7z" --quiet
if [ $? -eq 0 ]; then
    echo "Backup $BACKUP_NAME verified successfully"
else
    echo "CRITICAL: Backup verification failed!" >&2
    exit 5
fi
```

### Cron Job Integration
```bash
# Weekly verification (add to crontab)
0 2 * * 0 /usr/local/bin/cpack verify /backup/*.7z --quiet

# Monthly archive cleanup with verification
0 3 1 * * find /archive -name "*.7z" -mtime +90 -exec cpack verify {} --quiet \;
```

### CI/CD Pipeline
```yaml
# GitHub Actions - Archival workflow
- name: Create Release Archive
  run: |
    cpack create ./dist --output-dir ./release --name "app-${{ github.ref_name }}"
    cpack verify "./release/app-${{ github.ref_name }}.7z"

- name: Upload Archive
  uses: actions/upload-artifact@v3
  with:
    name: coldpack-archive
    path: ./release/
```

## Troubleshooting

### Quick Diagnostics
```bash
# Check installation
cpack --version

# Verify all commands available
cpack --help

# Test basic functionality
mkdir test-dir && echo "test" > test-dir/file.txt
cpack create test-dir --quiet
```

### Common Solutions
```bash
# Permissions: Run with proper permissions
sudo cpack create /restricted/data --output-dir /backup

# Space: Check and free disk space
df -h && cpack create data/ --output-dir /large-partition

# Performance: Adjust threads for your system
cpack create large-data/ --threads 8  # Limit threads
cpack create small-data/ --threads 0  # Use all cores
```

### Getting Help
```bash
# Command-specific help
cpack create --help
cpack list --help

# General help and version
cpack --help
cpack --version
```

---

**Next Steps:**
- 📚 [Usage Examples](EXAMPLES.md) - Real-world scenarios and workflows
- 🏗️ [Architecture Guide](ARCHITECTURE.md) - Technical details and advanced configuration
- 📋 [Installation Guide](INSTALLATION.md) - Setup and deployment instructions
