# Usage Examples

Usage scenarios and workflows for coldpack v0.1.1.

## Table of Contents

- [Quick Start](#quick-start)
- [Archive Creation](#archive-creation)
- [Extraction & Recovery](#extraction--recovery)
- [File Management](#file-management)
- [Workflows](#workflows)
- [Automation & Integration](#automation--integration)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting Scenarios](#troubleshooting-scenarios)

## Quick Start

### Your First 7z Archive

```bash
# Create test data
mkdir sample_documents
echo "# Project Documentation" > sample_documents/README.md
echo "Configuration settings" > sample_documents/config.json
mkdir sample_documents/reports
echo "Annual report data" > sample_documents/reports/annual.txt

# Create 7z cold storage archive (automatic dynamic optimization)
cpack create sample_documents/
# Output: Creates sample_documents/sample_documents.7z with full verification

# Verify the archive integrity
cpack verify sample_documents/sample_documents.7z
# Output: ✓ 4-layer verification complete

# List archive contents
cpack list sample_documents/sample_documents.7z
# Output: File listing with metadata
```

### Essential Workflow

```bash
# 1. Create archive with dynamic compression
cpack create /path/to/important/documents

# 2. Verify 4-layer integrity
cpack verify documents/documents.7z

# 3. Extract with automatic parameter recovery
cpack extract documents/documents.7z --output-dir ./restored

# 4. Archive metadata display
cpack info documents/documents.7z
```

## Archive Creation

### Multi-Format Input Processing

```bash
# Archive directories with intelligent system file filtering
cpack create ./project_source/        # Excludes .git, .DS_Store, etc.
cpack create /home/user/documents/    # Cross-platform compatibility

# Convert legacy archive formats to 7z cold storage
cpack create legacy_backup.zip --output-dir /cold-storage
cpack create old_data.tar.gz --name converted_data
cpack create important.rar --output-dir /archives

# Batch conversion with progress tracking
for archive in *.zip *.tar.gz *.rar; do
    [ -f "$archive" ] && cpack create "$archive" --output-dir /converted
done
```

### Dynamic Compression Optimization

coldpack automatically selects optimal compression based on file size:

```bash
# Small files (< 256KB) - Level 1, Dict 128k (automatic)
cpack create small_configs/

# Medium files (1-8MB) - Level 5, Dict 4m (automatic)
cpack create documents/

# Large datasets (> 2GB) - Level 9, Dict 512m (automatic)
cpack create large_dataset/

# Manual override for special cases
cpack create media_files/ --level 3 --dict 1m     # Fast for pre-compressed
cpack create source_code/ --level 9 --dict 256m   # Maximum for text files
```

### Output Organization

```bash
# Structured backup with timestamps
DATE=$(date +%Y%m%d_%H%M%S)
cpack create /critical/data --output-dir /backup --name "critical_backup_$DATE"

# Organized archive hierarchy
mkdir -p "/cold-storage/$(date +%Y/%m)"
cpack create ./project/ --output-dir "/cold-storage/$(date +%Y/%m)" --name "project_$(date +%Y%m%d)"

# Naming conventions
cpack create /database/dump --name "db_prod_$(hostname)_$(date +%Y%m%d)" --output-dir /archives
```

### Verification Configuration

```bash
# Maximum security with high PAR2 redundancy
cpack create sensitive_data/ --par2-redundancy 20    # 20% recovery capability

# Performance-optimized for CI/CD
cpack create build_artifacts/ --level 3 --no-verify-par2

# Selective verification (customize for workflow)
cpack create temp_data/ --no-verify-blake3 --no-verify-par2

# Full verification (default)
cpack create critical_documents/    # All 4 layers enabled
```

## Smart Extraction & Recovery

### Automatic Parameter Recovery

```bash
# coldpack archives automatically restore original compression parameters
cpack extract backup.7z --output-dir /restored
# Uses original: level 7, dict 64m, threads all, method LZMA2

# Pre-verification for critical data
cpack extract sensitive_archive.7z --verify --output-dir /safe-restore
# Performs 4-layer verification before extraction

# Legacy format extraction (no parameter recovery)
cpack extract old_backup.zip --output-dir /converted
cpack extract data.tar.gz --output-dir /extracted
```

### Recovery Scenarios

```bash
# Basic PAR2 repair for corrupted archives
cpack repair damaged_archive.7z

# Repair with post-verification (recommended)
cpack repair important_data.7z --verify-after

# Batch repair for multiple damaged files
for damaged in /backup/*.7z; do
    echo "Repairing: $damaged"
    cpack repair "$damaged" --verify-after --quiet
done
```

### Cross-Platform Extraction

```bash
# Windows to Linux/macOS (automatic filename sanitization)
cpack extract windows_backup.7z --output-dir /linux-safe

# Preserve permissions and timestamps
cpack extract unix_archive.7z --output-dir /restored

# Handle Unicode filenames correctly
cpack extract international_文档.7z --output-dir /unicode-safe
```

## File Management

### File Listing

```bash
# Basic archive contents
cpack list documents.7z

# Paginated listing for large archives
cpack list massive_dataset.7z --limit 50 --offset 200

# Filter specific file types
cpack list photos.7z --filter "*.jpg" --filter "*.png"
cpack list documents.7z --filter "*.pdf" --filter "*.docx"

# Directory structure analysis
cpack list backup.7z --dirs-only              # Directories only
cpack list archive.7z --files-only            # Files only
cpack list dataset.7z --summary-only          # Statistics only

# Script-friendly output
cpack list archive.7z --files-only --quiet | grep "\.log$"
```

### Archive Analysis & Metadata

```bash
# Archive metadata display
cpack info project_backup.7z

# Comprehensive information with verbose details
cpack info critical_data.7z --verbose

# Quick status check for scripts
cpack info backup.7z --quiet && echo "Archive OK"

# Batch archive analysis
for archive in /backup/*.7z; do
    echo "=== $(basename "$archive") ==="
    cpack info "$archive" --quiet
done
```

### Verification Workflows

```bash
# Complete 4-layer verification
cpack verify documents.7z
# ✓ 7z integrity ✓ SHA256 ✓ BLAKE3 ✓ PAR2

# Batch verification with detailed progress
cpack verify /backup/*.7z --verbose

# Script-friendly verification
cpack verify critical_data.7z --quiet
if [ $? -eq 0 ]; then
    echo "Archive integrity confirmed"
else
    echo "CRITICAL: Archive verification failed!"
    exit 5
fi

# Automated verification with email alerts
FAILED_ARCHIVES=""
for archive in /backup/*.7z; do
    if ! cpack verify "$archive" --quiet; then
        FAILED_ARCHIVES="$FAILED_ARCHIVES\n$(basename "$archive")"
    fi
done
[ -n "$FAILED_ARCHIVES" ] && echo -e "Failed archives:$FAILED_ARCHIVES" | mail -s "Backup Verification Failed" admin@company.com
```

## Workflows

### Database Backup & Archival

```bash
#!/bin/bash
# Database backup with coldpack
set -euo pipefail

DB_NAME="production_db"
BACKUP_DIR="/backup/database"
ARCHIVE_DIR="/cold-storage/database"
DATE=$(date +%Y%m%d_%H%M%S)

# Create database dump
echo "Creating database dump..."
pg_dump "$DB_NAME" > "/tmp/${DB_NAME}_${DATE}.sql"

# Create 7z archive with maximum compression
echo "Creating cold storage archive..."
cpack create "/tmp/${DB_NAME}_${DATE}.sql" \
    --output-dir "$ARCHIVE_DIR" \
    --name "${DB_NAME}_backup_${DATE}" \
    --level 9 \
    --dict 512m \
    --par2-redundancy 15

# Verify archive integrity
echo "Verifying archive integrity..."
cpack verify "$ARCHIVE_DIR/${DB_NAME}_backup_${DATE}.7z"

# Clean up temporary dump
rm "/tmp/${DB_NAME}_${DATE}.sql"

echo "Database backup complete: ${DB_NAME}_backup_${DATE}.7z"
```

### Document Management System

```bash
#!/bin/bash
# Corporate document archival workflow
set -euo pipefail

DOCS_ROOT="/shared/documents"
ARCHIVE_ROOT="/cold-storage/documents"
YEAR=$(date +%Y)
MONTH=$(date +%m)

# Create monthly archive structure
mkdir -p "$ARCHIVE_ROOT/$YEAR/$MONTH"

# Archive each department separately
for dept in hr finance engineering marketing; do
    if [ -d "$DOCS_ROOT/$dept" ]; then
        echo "Archiving $dept documents..."

        cpack create "$DOCS_ROOT/$dept" \
            --output-dir "$ARCHIVE_ROOT/$YEAR/$MONTH" \
            --name "${dept}_docs_${YEAR}${MONTH}" \
            --level 7 \
            --par2-redundancy 12

        # Verify and log
        if cpack verify "$ARCHIVE_ROOT/$YEAR/$MONTH/${dept}_docs_${YEAR}${MONTH}.7z" --quiet; then
            echo "✓ $dept archive verified successfully"
        else
            echo "✗ $dept archive verification FAILED" >&2
            exit 1
        fi
    fi
done

echo "Monthly document archival complete for $YEAR-$MONTH"
```

### Development Project Archival

```bash
#!/bin/bash
# Software project release archival
set -euo pipefail

PROJECT_NAME="myapp"
VERSION="$1"
BUILD_DIR="./dist"
RELEASE_DIR="/releases"
ARCHIVE_DIR="/cold-storage/releases"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "Creating release archive for $PROJECT_NAME v$VERSION"

# Create comprehensive project archive
cpack create "$BUILD_DIR" \
    --output-dir "$ARCHIVE_DIR" \
    --name "${PROJECT_NAME}_v${VERSION}_$(date +%Y%m%d)" \
    --level 9 \
    --dict 256m

# Archive source code separately
git archive --format=tar --prefix="${PROJECT_NAME}-${VERSION}/" HEAD | \
    gzip > "/tmp/${PROJECT_NAME}_source_${VERSION}.tar.gz"

cpack create "/tmp/${PROJECT_NAME}_source_${VERSION}.tar.gz" \
    --output-dir "$ARCHIVE_DIR" \
    --name "${PROJECT_NAME}_source_v${VERSION}"

# Verification
echo "Verifying release archives..."
cpack verify "$ARCHIVE_DIR/${PROJECT_NAME}_v${VERSION}_$(date +%Y%m%d).7z"
cpack verify "$ARCHIVE_DIR/${PROJECT_NAME}_source_v${VERSION}.7z"

# Clean up
rm "/tmp/${PROJECT_NAME}_source_${VERSION}.tar.gz"

echo "Release archival complete for v$VERSION"
```

## Automation & Integration

### Cron-Based Archive Maintenance

```bash
#!/bin/bash
# /etc/cron.daily/coldpack-maintenance
# Daily archive maintenance and verification

BACKUP_DIR="/backup"
ARCHIVE_DIR="/cold-storage"
LOG_FILE="/var/log/coldpack-maintenance.log"
MAX_AGE_DAYS=30

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== Archive Maintenance: $(date) ==="

# Verify all recent archives
echo "Verifying recent archives..."
find "$ARCHIVE_DIR" -name "*.7z" -mtime -7 | while read -r archive; do
    if cpack verify "$archive" --quiet; then
        echo "✓ $(basename "$archive")"
    else
        echo "✗ FAILED: $(basename "$archive")" >&2
    fi
done

# Archive old backups
echo "Archiving old backup files..."
find "$BACKUP_DIR" -name "*.sql" -o -name "*.dump" -mtime +1 | while read -r backup; do
    if [ -f "$backup" ]; then
        base_name=$(basename "$backup" | sed 's/\.[^.]*$//')
        cpack create "$backup" \
            --output-dir "$ARCHIVE_DIR/automated" \
            --name "auto_${base_name}_$(date +%Y%m%d)" \
            --level 7 \
            --quiet

        # Remove original after successful archival
        if cpack verify "$ARCHIVE_DIR/automated/auto_${base_name}_$(date +%Y%m%d).7z" --quiet; then
            rm "$backup"
            echo "Archived and removed: $(basename "$backup")"
        fi
    fi
done

echo "Archive maintenance completed"
```

### GitHub Actions Integration

```yaml
# .github/workflows/release-archive.yml
name: Create Release Archive

on:
  release:
    types: [published]

jobs:
  archive:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Install coldpack
      run: pip install coldpack

    - name: Build application
      run: |
        npm install
        npm run build

    - name: Create archive
      run: |
        cpack create ./dist \
          --output-dir ./release-archives \
          --name "app-${{ github.ref_name }}-$(date +%Y%m%d)" \
          --level 9 \
          --par2-redundancy 15

    - name: Verify archive integrity
      run: |
        cpack verify "./release-archives/app-${{ github.ref_name }}-$(date +%Y%m%d).7z"

    - name: Upload release archive
      uses: actions/upload-release-asset@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        upload_url: ${{ github.event.release.upload_url }}
        asset_path: "./release-archives/app-${{ github.ref_name }}-$(date +%Y%m%d).7z"
        asset_name: "app-${{ github.ref_name }}.7z"
        asset_content_type: application/x-7z-compressed
```

### Docker Integration

```dockerfile
# Dockerfile for coldpack-enabled backup container
FROM python:3.11-slim

# Install coldpack
RUN pip install coldpack

# Create backup script
COPY backup-script.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup-script.sh

# Set up cron for scheduled backups
RUN apt-get update && apt-get install -y cron
COPY crontab /etc/cron.d/backup-cron
RUN chmod 0644 /etc/cron.d/backup-cron && crontab /etc/cron.d/backup-cron

VOLUME ["/backup", "/cold-storage"]
CMD ["cron", "-f"]
```

```bash
# backup-script.sh (used in Docker container)
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)

# Archive application data
cpack create /app/data \
    --output-dir /cold-storage \
    --name "app_data_$DATE" \
    --level 7

# Verify archive
cpack verify "/cold-storage/app_data_$DATE.7z" --quiet

# Log success
echo "Backup completed: app_data_$DATE.7z" >> /backup/backup.log
```

## Performance Optimization

### Resource Management

```bash
# Resource-constrained environments (VPS, containers)
cpack create large_dataset/ --level 3 --dict 16m --threads 2

# High-performance workstations (maximize compression)
cpack create source_code/ --level 9 --dict 512m --threads 0

# Network storage optimization (balance speed vs compression)
cpack create network_data/ --level 5 --dict 64m --threads 4

# SSD optimization (reduce write cycles)
COLDPACK_TEMP_DIR=/tmp/ramdisk cpack create important_data/
```

### File Size-Based Strategies

```bash
# Small files (< 100MB) - prioritize speed
find /configs -name "*.conf" -exec cpack create {} --level 1 --dict 1m \;

# Medium files (100MB - 1GB) - balanced approach
cpack create documents/ --level 5 --dict 32m

# Large files (1GB+) - maximize compression
cpack create database_dumps/ --level 9 --dict 512m --threads 8

# Pre-compressed files (media, archives) - minimal compression
cpack create media_collection/ --level 1 --dict 128k --no-verify-par2
```

### Batch Processing Optimization

```bash
#!/bin/bash
# Optimized batch processing with resource management
set -euo pipefail

MAX_PARALLEL=4
ARCHIVE_QUEUE=()
CURRENT_JOBS=0

process_archive() {
    local source="$1"
    echo "Processing: $source"

    # Determine optimal settings based on source size
    size=$(du -sb "$source" | cut -f1)
    if [ "$size" -lt 104857600 ]; then    # < 100MB
        level=3; dict="4m"
    elif [ "$size" -lt 1073741824 ]; then # < 1GB
        level=5; dict="32m"
    else                                  # >= 1GB
        level=7; dict="128m"
    fi

    cpack create "$source" \
        --level "$level" \
        --dict "$dict" \
        --threads 2 \
        --output-dir /cold-storage \
        --quiet

    echo "Completed: $source"
}

# Process directories in parallel
for dir in /data/*/; do
    if [ -d "$dir" ]; then
        if [ "$CURRENT_JOBS" -ge "$MAX_PARALLEL" ]; then
            wait -n  # Wait for any job to complete
            ((CURRENT_JOBS--))
        fi

        process_archive "$dir" &
        ((CURRENT_JOBS++))
    fi
done

# Wait for all remaining jobs
wait
echo "Batch processing completed"
```

### Memory Usage Optimization

```bash
# Large file processing with memory constraints
ulimit -v 2097152  # Limit virtual memory to 2GB
cpack create huge_dataset/ --level 5 --dict 64m --threads 2

# Streaming processing for very large files
export COLDPACK_STREAMING_MODE=1
cpack create massive_video_collection/ --level 3 --dict 16m

# Monitor memory usage during processing
(
    cpack create large_data/ --level 7 --verbose &
    PID=$!

    while kill -0 $PID 2>/dev/null; do
        ps -p $PID -o pid,vsz,rss,pcpu --no-headers
        sleep 5
    done
) 2>/dev/null
```

## Troubleshooting Scenarios

### Corruption Recovery

```bash
#!/bin/bash
# Comprehensive corruption recovery workflow
set -euo pipefail

ARCHIVE="damaged_archive.7z"
BACKUP_DIR="/recovery"

echo "=== Corruption Recovery for $ARCHIVE ==="

# Step 1: Attempt basic verification
echo "1. Checking archive integrity..."
if cpack verify "$ARCHIVE" --quiet; then
    echo "✓ Archive is intact, no recovery needed"
    exit 0
fi

# Step 2: Check if PAR2 files exist
if [ -f "${ARCHIVE}.par2" ]; then
    echo "2. PAR2 recovery files found, attempting repair..."

    # Create backup before repair
    cp "$ARCHIVE" "${BACKUP_DIR}/$(basename "$ARCHIVE").backup"

    # Attempt PAR2 repair
    if cpack repair "$ARCHIVE" --verify-after; then
        echo "✓ Archive successfully repaired using PAR2"
        exit 0
    else
        echo "✗ PAR2 repair failed"
    fi
else
    echo "2. No PAR2 recovery files found"
fi

# Step 3: Attempt partial extraction
echo "3. Attempting partial data recovery..."
mkdir -p "${BACKUP_DIR}/partial_recovery"

if cpack extract "$ARCHIVE" --output-dir "${BACKUP_DIR}/partial_recovery" --force; then
    echo "✓ Partial extraction successful"
    echo "Recovered files located in: ${BACKUP_DIR}/partial_recovery"

    # Try to re-archive recovered data
    cpack create "${BACKUP_DIR}/partial_recovery" \
        --output-dir "${BACKUP_DIR}" \
        --name "recovered_$(basename "$ARCHIVE" .7z)" \
        --level 7

    echo "✓ Re-archived recovered data"
else
    echo "✗ Partial extraction failed - archive severely corrupted"
    exit 1
fi
```

### Performance Troubleshooting

```bash
#!/bin/bash
# Performance diagnostics and optimization
set -euo pipefail

ARCHIVE_SOURCE="$1"
TEST_OUTPUT="/tmp/coldpack_perf_test"

if [ -z "$ARCHIVE_SOURCE" ]; then
    echo "Usage: $0 <source_directory>"
    exit 1
fi

echo "=== Performance Analysis for: $ARCHIVE_SOURCE ==="

# System resource check
echo "1. System Resources:"
echo "   CPU cores: $(nproc)"
echo "   Available RAM: $(free -h | awk '/^Mem:/ {print $7}')"
echo "   Temp space: $(df -h /tmp | awk 'NR==2 {print $4}')"
echo ""

# Source analysis
echo "2. Source Analysis:"
SOURCE_SIZE=$(du -sh "$ARCHIVE_SOURCE" | cut -f1)
FILE_COUNT=$(find "$ARCHIVE_SOURCE" -type f | wc -l)
echo "   Total size: $SOURCE_SIZE"
echo "   File count: $FILE_COUNT"
echo ""

# Performance test with different settings
echo "3. Performance Testing:"
for level in 1 3 5 7 9; do
    echo "   Testing compression level $level..."

    start_time=$(date +%s)

    cpack create "$ARCHIVE_SOURCE" \
        --output-dir "$TEST_OUTPUT" \
        --name "test_level_$level" \
        --level "$level" \
        --quiet \
        --no-verify-par2

    end_time=$(date +%s)
    duration=$((end_time - start_time))

    if [ -f "$TEST_OUTPUT/test_level_$level.7z" ]; then
        compressed_size=$(du -sh "$TEST_OUTPUT/test_level_$level.7z" | cut -f1)
        echo "     Level $level: ${duration}s, Size: $compressed_size"
        rm -f "$TEST_OUTPUT/test_level_$level.7z"
    else
        echo "     Level $level: FAILED"
    fi
done

# Cleanup
rm -rf "$TEST_OUTPUT"

echo ""
echo "4. Recommendations:"
if [ "$FILE_COUNT" -gt 10000 ]; then
    echo "   - Large file count detected: consider --level 3-5 for speed"
fi

available_ram_kb=$(free | awk '/^Mem:/ {print $7}')
if [ "$available_ram_kb" -lt 2097152 ]; then  # < 2GB
    echo "   - Limited RAM: use --dict 32m or smaller"
fi

echo "   - Optimal settings: --level 5 --dict 64m --threads $(nproc)"
```

### Disk Space Management

```bash
#!/bin/bash
# Intelligent disk space management during archival
set -euo pipefail

SOURCE="$1"
OUTPUT_DIR="$2"

if [ -z "$SOURCE" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <source> <output_dir>"
    exit 1
fi

echo "=== Disk Space Management ==="

# Calculate source size
SOURCE_SIZE_KB=$(du -sk "$SOURCE" | cut -f1)
echo "Source size: $((SOURCE_SIZE_KB / 1024)) MB"

# Check available space
AVAILABLE_KB=$(df "$OUTPUT_DIR" | awk 'NR==2 {print $4}')
echo "Available space: $((AVAILABLE_KB / 1024)) MB"

# Estimate required space (source + temp + compressed + verification files)
REQUIRED_KB=$((SOURCE_SIZE_KB * 3))  # Conservative estimate
echo "Estimated required: $((REQUIRED_KB / 1024)) MB"

if [ "$AVAILABLE_KB" -lt "$REQUIRED_KB" ]; then
    echo "⚠️  Insufficient disk space!"
    echo "Attempting space-saving measures..."

    # Use alternative temp directory if available
    for temp_dir in /tmp /var/tmp "$HOME/temp"; do
        if [ -d "$temp_dir" ]; then
            temp_available=$(df "$temp_dir" | awk 'NR==2 {print $4}')
            if [ "$temp_available" -gt "$SOURCE_SIZE_KB" ]; then
                echo "Using alternative temp directory: $temp_dir"
                export COLDPACK_TEMP_DIR="$temp_dir"
                break
            fi
        fi
    done

    # Use lower compression to reduce processing time and temp space
    echo "Using fast compression to minimize temp space usage"
    cpack create "$SOURCE" \
        --output-dir "$OUTPUT_DIR" \
        --level 3 \
        --dict 16m \
        --no-verify-par2
else
    echo "✓ Sufficient disk space available"
    cpack create "$SOURCE" --output-dir "$OUTPUT_DIR"
fi
```

### Network Storage Optimization

```bash
#!/bin/bash
# Optimize coldpack for network storage (NFS, SMB, etc.)
set -euo pipefail

NETWORK_STORAGE="$1"
LOCAL_TEMP="/tmp/coldpack_network"
SOURCE="$2"

echo "=== Network Storage Optimization ==="

# Create local temp directory
mkdir -p "$LOCAL_TEMP"

# Use local temp for processing, then transfer
echo "Processing locally to minimize network I/O..."
cpack create "$SOURCE" \
    --output-dir "$LOCAL_TEMP" \
    --level 7 \
    --verbose

# Verify locally before network transfer
ARCHIVE_NAME=$(basename "$SOURCE")
if cpack verify "$LOCAL_TEMP/$ARCHIVE_NAME/$ARCHIVE_NAME.7z" --quiet; then
    echo "✓ Local verification successful, transferring to network storage..."

    # Transfer complete archive directory
    rsync -av --progress "$LOCAL_TEMP/$ARCHIVE_NAME/" "$NETWORK_STORAGE/$ARCHIVE_NAME/"

    # Verify after network transfer
    if cpack verify "$NETWORK_STORAGE/$ARCHIVE_NAME/$ARCHIVE_NAME.7z" --quiet; then
        echo "✓ Network transfer verification successful"
        rm -rf "$LOCAL_TEMP/$ARCHIVE_NAME"
    else
        echo "✗ Network transfer verification failed"
        exit 1
    fi
else
    echo "✗ Local verification failed"
    exit 1
fi
```

---

## Summary

coldpack v0.1.1 provides 7z cold storage with optimizations:

- **🚀 Dynamic Compression**: 7-tier intelligent optimization
- **🛡️ 4-Layer Verification**: Complete integrity assurance
- **🔧 Cross-Platform**: Windows, macOS, Linux compatibility
- **⚡ Performance**: Multi-core processing and optimization
- **🏗️ Integration**: Automation-ready with tooling

**Next Steps:**
- 📖 [Installation Guide](INSTALLATION.md) - Complete setup instructions
- 📋 [CLI Reference](CLI_REFERENCE.md) - Detailed command documentation
- 🏗️ [Architecture Guide](ARCHITECTURE.md) - Technical implementation details
