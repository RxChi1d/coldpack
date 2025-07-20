# Usage Examples

Comprehensive examples for using coldpack in various scenarios.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Archive Creation](#archive-creation)
- [Archive Extraction](#archive-extraction)
- [Verification and Repair](#verification-and-repair)
- [Batch Operations](#batch-operations)
- [Integration Scenarios](#integration-scenarios)
- [Advanced Configuration](#advanced-configuration)
- [Performance Optimization](#performance-optimization)
- [Error Handling](#error-handling)

## Basic Usage

### Your First Archive

```bash
# Create a simple archive from a directory
mkdir sample_data
echo "Hello, coldpack!" > sample_data/readme.txt
echo "Important data" > sample_data/data.txt

# Archive the directory
cpack archive sample_data/
# Output: Archives created in ./archives/sample_data/
```

### Quick Start Workflow

```bash
# 1. Create archive
cpack archive /path/to/important/data

# 2. Verify integrity
cpack verify ./archives/data/data.tar.zst

# 3. Extract when needed
cpack extract ./archives/data/data.tar.zst -o ./restored
```

## Archive Creation

### From Different Source Types

```bash
# Archive a directory
cpack archive ./project_files/
cpack archive /home/user/documents/

# Archive existing archive files
cpack archive backup.7z
cpack archive data.zip
cpack archive old_archive.tar.gz

# Multiple sources (process separately)
for source in *.zip; do
    cpack archive "$source"
done
```

### Custom Output Locations

```bash
# Specify output directory
cpack archive ./data/ -o /backup/archives/

# Custom archive name
cpack archive ./data/ -n "project_backup_$(date +%Y%m%d)"

# Organized by date
mkdir -p "/backup/$(date +%Y/%m)"
cpack archive ./data/ -o "/backup/$(date +%Y/%m)"
```

### Compression Settings

```bash
# Maximum compression (takes longer)
cpack archive ./data/ -l 22 --ultra

# Balanced compression (recommended)
cpack archive ./data/ -l 19

# Fast compression (for temporary archives)
cpack archive ./data/ -l 5

# No compression (for already compressed data)
cpack archive ./media_files/ -l 1
```

### Threading and Performance

```bash
# Use all CPU cores (default)
cpack archive ./data/

# Limit threads for background processing
cpack archive ./large_dataset/ -t 2

# Maximum threads for urgent processing
cpack archive ./data/ -t $(nproc)

# Single-threaded for resource-constrained systems
cpack archive ./data/ -t 1
```

## Archive Extraction

### Basic Extraction

```bash
# Extract to default location (./extracted/)
cpack extract archive.tar.zst

# Extract to specific directory
cpack extract archive.tar.zst -o /tmp/restore

# Extract with verification first
cpack extract archive.tar.zst --verify
```

### Handling Different Archive Types

```bash
# coldpack can extract many formats
cpack extract legacy_backup.7z
cpack extract download.zip
cpack extract source.tar.gz
cpack extract database_backup.tar.xz

# All extract to standardized directory structure
ls ./extracted/
```

### Batch Extraction

```bash
# Extract all archives in directory
find ./archives/ -name "*.tar.zst" -exec cpack extract {} \;

# Extract with custom output organization
for archive in *.tar.zst; do
    name=$(basename "$archive" .tar.zst)
    cpack extract "$archive" -o "./restored/$name"
done
```

## Verification and Repair

### Regular Verification

```bash
# Full 5-layer verification
cpack verify archive.tar.zst

# Quick verification (faster)
cpack verify archive.tar.zst --quick

# Batch verification
cpack verify ./archives/*/*.tar.zst

# Verification with detailed output
cpack verify archive.tar.zst -v
```

### Automated Verification Scripts

```bash
#!/bin/bash
# weekly_verify.sh - Weekly archive verification
BACKUP_DIR="/backup/archives"
LOG_FILE="/var/log/coldpack_verify.log"

echo "$(date): Starting verification" >> "$LOG_FILE"

for archive in "$BACKUP_DIR"/*/*.tar.zst; do
    if cpack verify "$archive" --quiet; then
        echo "$(date): OK - $archive" >> "$LOG_FILE"
    else
        echo "$(date): FAILED - $archive" >> "$LOG_FILE"
        # Send alert email
        mail -s "Archive verification failed: $archive" admin@company.com < /dev/null
    fi
done

echo "$(date): Verification complete" >> "$LOG_FILE"
```

### Repair Operations

```bash
# Repair corrupted archive
cpack repair corrupted_archive.tar.zst

# Repair with verification after
cpack repair archive.tar.zst --verify-after

# Repair with backup of original
cpack repair archive.tar.zst --backup

# Force repair (even if verification passes)
cpack repair archive.tar.zst --force
```

## Batch Operations

### Processing Multiple Directories

```bash
#!/bin/bash
# backup_projects.sh - Archive multiple project directories

PROJECTS_DIR="/home/user/projects"
BACKUP_DIR="/backup/projects"

for project in "$PROJECTS_DIR"/*/; do
    project_name=$(basename "$project")
    echo "Archiving $project_name..."

    cpack archive "$project" \
        -o "$BACKUP_DIR" \
        -n "${project_name}_$(date +%Y%m%d)" \
        --quiet
done

echo "All projects archived to $BACKUP_DIR"
```

### Parallel Processing

```bash
# Using GNU parallel for maximum efficiency
find /data -maxdepth 1 -type d -name "dataset_*" | \
    parallel --jobs 4 cpack archive {} -o /backup/datasets/

# Using xargs for simpler parallel processing
find . -name "*.7z" | xargs -P 4 -I {} cpack archive {}

# Manual parallel processing with background jobs
for dir in dataset_*/; do
    cpack archive "$dir" &
    # Limit concurrent jobs
    (($(jobs -r | wc -l) >= 4)) && wait
done
wait  # Wait for all jobs to complete
```

### Archive Migration

```bash
#!/bin/bash
# migrate_archives.sh - Convert old archives to coldpack format

OLD_ARCHIVES_DIR="/old_backups"
NEW_ARCHIVES_DIR="/new_backups"

for old_archive in "$OLD_ARCHIVES_DIR"/*.{7z,zip,tar.gz}; do
    if [[ -f "$old_archive" ]]; then
        echo "Converting $(basename "$old_archive")..."
        cpack archive "$old_archive" -o "$NEW_ARCHIVES_DIR"

        # Verify the new archive
        new_name=$(basename "$old_archive" | sed 's/\.[^.]*$//')
        if cpack verify "$NEW_ARCHIVES_DIR/$new_name/$new_name.tar.zst"; then
            echo "Migration successful: $old_archive"
            # Optionally remove old archive after successful verification
            # rm "$old_archive"
        else
            echo "Migration failed: $old_archive"
        fi
    fi
done
```

## Integration Scenarios

### Git Hook Integration

```bash
#!/bin/bash
# .git/hooks/pre-push - Archive project before push

# Archive current state
git archive --format=tar HEAD | gzip > "/tmp/pre-push-backup.tar.gz"
cpack archive "/tmp/pre-push-backup.tar.gz" -o "$HOME/git-backups" -n "$(basename $(pwd))_$(date +%Y%m%d_%H%M%S)"

# Clean up temporary file
rm "/tmp/pre-push-backup.tar.gz"

echo "Project archived before push"
```

### Database Backup Integration

```bash
#!/bin/bash
# db_backup.sh - Database backup with coldpack

DB_NAME="production_db"
BACKUP_DIR="/backup/database"
DATE=$(date +%Y%m%d_%H%M%S)

# Create database dump
pg_dump "$DB_NAME" > "/tmp/${DB_NAME}_${DATE}.sql"

# Compress and archive
gzip "/tmp/${DB_NAME}_${DATE}.sql"
cpack archive "/tmp/${DB_NAME}_${DATE}.sql.gz" \
    -o "$BACKUP_DIR" \
    -n "${DB_NAME}_${DATE}" \
    -l 22 --ultra

# Clean up temporary file
rm "/tmp/${DB_NAME}_${DATE}.sql.gz"

# Verify the archive
cpack verify "$BACKUP_DIR/${DB_NAME}_${DATE}/${DB_NAME}_${DATE}.tar.zst"

echo "Database backup completed: ${DB_NAME}_${DATE}"
```

### CI/CD Pipeline Integration

```yaml
# .github/workflows/backup.yml
name: Backup Build Artifacts

on:
  release:
    types: [published]

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install coldpack
        run: pip install coldpack

      - name: Build project
        run: |
          mkdir build
          # Your build commands here
          echo "Build artifacts" > build/artifacts.txt

      - name: Create archive
        run: |
          cpack archive ./build/ -o ./archives -n "release_${{ github.event.release.tag_name }}"

      - name: Verify archive
        run: |
          cpack verify ./archives/release_${{ github.event.release.tag_name }}/release_${{ github.event.release.tag_name }}.tar.zst

      - name: Upload archive
        uses: actions/upload-artifact@v3
        with:
          name: release-archive
          path: ./archives/
```

### Cron Job Automation

```bash
# Add to crontab: crontab -e

# Daily backup at 2 AM
0 2 * * * /usr/local/bin/cpack archive /important/data -o /backup/daily -n "daily_$(date +\%Y\%m\%d)" --quiet

# Weekly verification on Sundays at 3 AM
0 3 * * 0 /usr/local/bin/cpack verify /backup/daily/*.tar.zst --quiet || echo "Weekly verification failed" | mail -s "Backup Alert" admin@company.com

# Monthly cleanup - keep only last 3 months
0 4 1 * * find /backup/daily -name "*.tar.zst" -mtime +90 -delete
```

## Advanced Configuration

### Environment Configuration

```bash
# ~/.bashrc or ~/.zshrc
export COLDPACK_DEFAULT_OUTPUT="/backup/archives"
export COLDPACK_COMPRESSION_LEVEL=19
export COLDPACK_THREADS=8
export COLDPACK_TEMP_DIR="/fast/ssd/temp"

# Project-specific configuration
# coldpack.toml in project directory
[compression]
level = 22
ultra_mode = true
threads = 16

[processing]
par2_redundancy = 15
verify_integrity = true

[output]
organize_by_date = true
preserve_structure = true
```

### Custom Wrapper Scripts

```bash
#!/bin/bash
# cold_backup.sh - Custom wrapper for standardized backups

set -e

SCRIPT_NAME=$(basename "$0")
SOURCE="$1"
DEST="${2:-/backup/cold_storage}"

usage() {
    echo "Usage: $SCRIPT_NAME <source> [destination]"
    echo "Create a standardized cold storage backup"
    exit 1
}

[[ -z "$SOURCE" ]] && usage

# Validate source exists
[[ ! -e "$SOURCE" ]] && { echo "Error: Source does not exist: $SOURCE"; exit 1; }

# Create timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SOURCE_NAME=$(basename "$SOURCE")

echo "Creating cold storage backup..."
echo "Source: $SOURCE"
echo "Destination: $DEST"
echo "Timestamp: $TIMESTAMP"

# Create archive with standardized naming
cpack archive "$SOURCE" \
    -o "$DEST" \
    -n "${SOURCE_NAME}_${TIMESTAMP}" \
    -l 22 --ultra \
    --verbose

# Verify immediately
ARCHIVE_PATH="$DEST/${SOURCE_NAME}_${TIMESTAMP}/${SOURCE_NAME}_${TIMESTAMP}.tar.zst"
echo "Verifying archive..."
cpack verify "$ARCHIVE_PATH" --verbose

echo "Cold storage backup completed successfully!"
echo "Archive: $ARCHIVE_PATH"
```

## Performance Optimization

### Large File Optimization

```bash
# For very large files (>10GB)
cpack archive huge_dataset/ \
    -l 12 \                    # Lower compression for speed
    -t $(nproc) \             # Use all cores
    --verbose

# For maximum compression (archival storage)
cpack archive important_data/ \
    -l 22 --ultra \           # Maximum compression
    -t 2 \                    # Fewer threads to avoid memory pressure
    --verbose
```

### Memory-Constrained Environments

```bash
# Reduce memory usage
export COLDPACK_TEMP_DIR="/tmp"  # Use fast temporary storage
cpack archive large_data/ \
    -l 15 \                      # Moderate compression
    -t 1 \                       # Single thread
    --quiet                      # Reduce output overhead
```

### SSD vs HDD Optimization

```bash
# For SSD storage (fast random access)
cpack archive data/ -l 19 -t $(nproc) --ultra

# For HDD storage (optimize for sequential access)
cpack archive data/ -l 15 -t 4

# Use SSD for temporary files, HDD for final storage
export COLDPACK_TEMP_DIR="/ssd/temp"
cpack archive data/ -o "/hdd/archives" -l 22 --ultra
```

## Error Handling

### Robust Backup Script

```bash
#!/bin/bash
# robust_backup.sh - Backup with comprehensive error handling

set -euo pipefail  # Exit on error, undefined vars, pipe failures

SOURCE="$1"
BACKUP_DIR="${2:-/backup}"
LOG_FILE="/var/log/coldpack_backup.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $*"
    exit 1
}

cleanup() {
    if [[ -n "${TEMP_DIR:-}" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        log "Cleaned up temporary directory: $TEMP_DIR"
    fi
}

trap cleanup EXIT

# Validation
[[ -z "$SOURCE" ]] && error_exit "Source directory required"
[[ ! -e "$SOURCE" ]] && error_exit "Source does not exist: $SOURCE"
[[ ! -d "$BACKUP_DIR" ]] && error_exit "Backup directory does not exist: $BACKUP_DIR"

# Check available space
SOURCE_SIZE=$(du -sb "$SOURCE" | cut -f1)
AVAILABLE_SPACE=$(df -B1 "$BACKUP_DIR" | awk 'NR==2 {print $4}')
REQUIRED_SPACE=$((SOURCE_SIZE * 3))  # Conservative estimate

if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
    error_exit "Insufficient space. Required: $REQUIRED_SPACE, Available: $AVAILABLE_SPACE"
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d -t coldpack_backup.XXXXXX)
export COLDPACK_TEMP_DIR="$TEMP_DIR"

log "Starting backup of $SOURCE"

# Create archive with retry logic
RETRY_COUNT=0
MAX_RETRIES=3

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    if cpack archive "$SOURCE" -o "$BACKUP_DIR" --quiet; then
        log "Archive creation successful"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        log "Archive creation failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
        [[ $RETRY_COUNT -eq $MAX_RETRIES ]] && error_exit "Archive creation failed after $MAX_RETRIES attempts"
        sleep 10
    fi
done

# Verify archive
ARCHIVE_NAME=$(basename "$SOURCE")
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME/$ARCHIVE_NAME.tar.zst"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
    error_exit "Archive not found at expected location: $ARCHIVE_PATH"
fi

log "Verifying archive integrity"
if cpack verify "$ARCHIVE_PATH" --quiet; then
    log "Archive verification successful"
    log "Backup completed: $ARCHIVE_PATH"
else
    error_exit "Archive verification failed"
fi
```

### Recovery Procedures

```bash
#!/bin/bash
# recovery.sh - Comprehensive recovery procedures

ARCHIVE="$1"
RECOVERY_DIR="${2:-./recovery}"

# Check if archive exists
[[ ! -f "$ARCHIVE" ]] && { echo "Archive not found: $ARCHIVE"; exit 1; }

echo "Starting recovery procedure for: $ARCHIVE"

# Step 1: Verify archive integrity
echo "Step 1: Verifying archive integrity..."
if cpack verify "$ARCHIVE" --quiet; then
    echo "✓ Archive integrity verified"
else
    echo "⚠ Archive verification failed, attempting repair..."

    # Step 2: Attempt repair
    if cpack repair "$ARCHIVE" --verify-after --quiet; then
        echo "✓ Archive repaired successfully"
    else
        echo "✗ Archive repair failed"
        echo "Manual intervention required:"
        echo "1. Check PAR2 files are present"
        echo "2. Verify sufficient PAR2 redundancy"
        echo "3. Check for additional corruption"
        exit 1
    fi
fi

# Step 3: Extract archive
echo "Step 2: Extracting archive..."
if cpack extract "$ARCHIVE" -o "$RECOVERY_DIR" --quiet; then
    echo "✓ Archive extracted successfully"
    echo "Recovery completed to: $RECOVERY_DIR"
else
    echo "✗ Extraction failed"
    exit 1
fi

# Step 4: Validation summary
echo ""
echo "Recovery Summary:"
echo "Archive: $ARCHIVE"
echo "Recovery Location: $RECOVERY_DIR"
echo "Files recovered: $(find "$RECOVERY_DIR" -type f | wc -l)"
echo "Total size: $(du -sh "$RECOVERY_DIR" | cut -f1)"
```

---

These examples cover most common use cases for coldpack. For specific scenarios not covered here, refer to the [CLI Reference](CLI_REFERENCE.md) or create custom wrapper scripts based on these patterns.
