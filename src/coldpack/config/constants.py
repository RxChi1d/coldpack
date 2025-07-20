"""Constants and default values for coldpack."""

# Compression defaults
DEFAULT_COMPRESSION_LEVEL = 19
DEFAULT_THREADS = 0  # Auto-detect
DEFAULT_LONG_MODE = True
DEFAULT_ULTRA_MODE = False

# PAR2 defaults
DEFAULT_PAR2_REDUNDANCY = 10  # 10% redundancy
PAR2_BLOCK_COUNT = 1  # Single recovery file for simplicity

# Supported formats
SUPPORTED_INPUT_FORMATS = {
    ".7z",
    ".zip",
    ".rar",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".tar.zst",
}

SUPPORTED_ARCHIVE_FORMATS = SUPPORTED_INPUT_FORMATS.union(
    {".gz", ".bz2", ".xz", ".zst", ".lz4", ".lzma"}
)

# Output format
OUTPUT_FORMAT = ".tar.zst"
OUTPUT_EXTENSIONS = {
    "archive": ".tar.zst",
    "sha256": ".sha256",
    "blake3": ".blake3",
    "par2": ".par2",
}

# File and directory management
TEMP_DIR_PREFIX = "coldpack_temp_"
MAX_FILENAME_LENGTH = 255
SAFE_FILENAME_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)

# Processing limits
MIN_DISK_SPACE_GB = 1.0  # Minimum 1GB free space required
PROGRESS_UPDATE_INTERVAL = 0.1  # Update progress every 100ms
HASH_CHUNK_SIZE = 65536  # 64KB chunks for hashing

# External tool requirements
REQUIRED_TOOLS = {
    "tar": "tar --help",
    "zstd": "zstd --help",
    "par2": "par2 --help",
    "sha256sum": "sha256sum --help",
    "b3sum": "b3sum --help",
}

# TAR format preferences (in order of preference)
TAR_FORMATS = ["posix", "gnu", "ustar"]

# Verification layer names
VERIFICATION_LAYERS = [
    "tar_header",
    "zstd_integrity",
    "sha256_hash",
    "blake3_hash",
    "par2_recovery",
]


# Error codes
class ExitCodes:
    """Exit codes for CLI operations."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    FILE_NOT_FOUND = 2
    PERMISSION_ERROR = 3
    INSUFFICIENT_SPACE = 4
    VERIFICATION_FAILED = 5
    TOOL_NOT_FOUND = 6
    INVALID_FORMAT = 7
    COMPRESSION_FAILED = 8
    EXTRACTION_FAILED = 9


# Logging configuration
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "1 week"
