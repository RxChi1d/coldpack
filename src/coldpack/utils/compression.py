"""Zstandard compression utilities with dynamic parameter optimization."""

import contextlib
import os
from pathlib import Path
from typing import Any, Optional, Union

import zstandard as zstd
from loguru import logger

from ..config.constants import HASH_CHUNK_SIZE
from ..config.settings import CompressionSettings


class CompressionError(Exception):
    """Base exception for compression operations."""

    pass


class ZstdCompressor:
    """High-performance Zstandard compressor with reusable context."""

    def __init__(self, settings: Optional[CompressionSettings] = None):
        """Initialize the compressor with settings.

        Args:
            settings: Compression settings, defaults to level 19
        """
        self.settings = settings or CompressionSettings()
        self._context: Optional[Any] = None
        self._create_context()

    def _create_context(self) -> None:
        """Create the zstd compression context."""
        try:
            self._context = zstd.ZstdCompressor(
                level=self.settings.level,
                threads=self.settings.threads if self.settings.threads > 0 else 0,
                write_checksum=True,  # Always enable checksums for integrity
                write_content_size=True,  # Include original size in frame
            )
            logger.debug(
                f"Created zstd compressor: level={self.settings.level}, "
                f"threads={self.settings.threads}, long_mode={self.settings.long_mode}, "
                f"long_distance={self.settings.long_distance}"
            )
        except Exception as e:
            raise CompressionError(f"Failed to create zstd compressor: {e}") from e

    def compress_file(
        self, input_path: Union[str, Path], output_path: Union[str, Path]
    ) -> None:
        """Compress a file using streaming to avoid memory issues.

        Args:
            input_path: Path to input file
            output_path: Path to output compressed file

        Raises:
            CompressionError: If compression fails
            FileNotFoundError: If input file doesn't exist
        """
        input_file = Path(input_path)
        output_file = Path(output_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        try:
            logger.info(f"Compressing {input_file} to {output_file}")

            # Get input file size for progress tracking
            input_size = input_file.stat().st_size

            with open(input_file, "rb") as ifh, open(output_file, "wb") as ofh:
                # Use streaming compression to handle large files
                assert self._context is not None
                self._context.copy_stream(ifh, ofh)

            # Verify output file was created
            if not output_file.exists():
                raise CompressionError("Output file was not created")

            output_size = output_file.stat().st_size
            ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0

            logger.success(
                f"Compression completed: {input_size} → {output_size} bytes "
                f"({ratio:.1f}% reduction)"
            )

        except OSError as e:
            raise CompressionError(f"File I/O error during compression: {e}") from e
        except Exception as e:
            # Clean up partial output file
            if output_file.exists():
                with contextlib.suppress(OSError):
                    output_file.unlink()
            raise CompressionError(f"Compression failed: {e}") from e

    def compress_data(self, data: bytes) -> bytes:
        """Compress bytes data.

        Args:
            data: Data to compress

        Returns:
            Compressed data

        Raises:
            CompressionError: If compression fails
        """
        try:
            assert self._context is not None
            result = self._context.compress(data)
            return bytes(result)
        except Exception as e:
            raise CompressionError(f"Data compression failed: {e}") from e


class ZstdDecompressor:
    """High-performance Zstandard decompressor with reusable context."""

    def __init__(self) -> None:
        """Initialize the decompressor."""
        self._context: Optional[Any] = None
        self._create_context()

    def _create_context(self) -> None:
        """Create the zstd decompression context."""
        try:
            self._context = zstd.ZstdDecompressor()
            logger.debug("Created zstd decompressor")
        except Exception as e:
            raise CompressionError(f"Failed to create zstd decompressor: {e}") from e

    def decompress_file(
        self, input_path: Union[str, Path], output_path: Union[str, Path]
    ) -> None:
        """Decompress a file using streaming to avoid memory issues.

        Args:
            input_path: Path to compressed input file
            output_path: Path to decompressed output file

        Raises:
            CompressionError: If decompression fails
            FileNotFoundError: If input file doesn't exist
        """
        input_file = Path(input_path)
        output_file = Path(output_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        try:
            logger.info(f"Decompressing {input_file} to {output_file}")

            with open(input_file, "rb") as ifh, open(output_file, "wb") as ofh:
                # Use streaming decompression
                assert self._context is not None
                self._context.copy_stream(ifh, ofh)

            # Verify output file was created
            if not output_file.exists():
                raise CompressionError("Output file was not created")

            logger.success(f"Decompression completed: {output_file}")

        except OSError as e:
            raise CompressionError(f"File I/O error during decompression: {e}") from e
        except Exception as e:
            # Clean up partial output file
            if output_file.exists():
                with contextlib.suppress(OSError):
                    output_file.unlink()
            raise CompressionError(f"Decompression failed: {e}") from e

    def decompress_data(self, data: bytes) -> bytes:
        """Decompress bytes data.

        Args:
            data: Compressed data

        Returns:
            Decompressed data

        Raises:
            CompressionError: If decompression fails
        """
        try:
            assert self._context is not None
            result = self._context.decompress(data)
            return bytes(result)
        except Exception as e:
            raise CompressionError(f"Data decompression failed: {e}") from e

    def test_integrity(self, file_path: Union[str, Path]) -> bool:
        """Test the integrity of a compressed file.

        Args:
            file_path: Path to the compressed file

        Returns:
            True if file integrity is valid

        Raises:
            CompressionError: If integrity check fails
            FileNotFoundError: If file doesn't exist
        """
        file_obj = Path(file_path)

        if not file_obj.exists():
            raise FileNotFoundError(f"File not found: {file_obj}")

        try:
            logger.debug(f"Testing zstd integrity: {file_obj}")

            with open(file_obj, "rb") as f:
                # Try to read and decompress the entire file
                # This will fail if the file is corrupted
                assert self._context is not None
                reader = self._context.stream_reader(f)
                while True:
                    chunk = reader.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break

            logger.debug(f"Zstd integrity check passed: {file_obj}")
            return True

        except Exception as e:
            logger.error(f"Zstd integrity check failed for {file_obj}: {e}")
            raise CompressionError(f"Integrity check failed: {e}") from e


def optimize_compression_settings(
    file_size: int, available_memory: Optional[int] = None
) -> CompressionSettings:
    """Optimize compression settings based on file size and available memory.

    Args:
        file_size: Size of file to compress in bytes
        available_memory: Available memory in bytes (optional)

    Returns:
        Optimized compression settings
    """
    # Default settings
    level = 19
    threads = 0  # Auto-detect
    long_mode = True
    ultra_mode = False

    # Adjust based on file size
    if file_size < 1024 * 1024:  # < 1MB - use fast compression
        level = 3
        long_mode = False
    elif file_size < 100 * 1024 * 1024:  # < 100MB - balanced
        level = 12
    elif file_size > 1024 * 1024 * 1024:  # > 1GB - use ultra for best compression
        level = 22
        ultra_mode = True

    # Adjust based on available memory if provided
    if available_memory is not None:
        memory_gb = available_memory / (1024**3)
        if memory_gb < 2.0:  # Less than 2GB memory
            long_mode = False
            if level > 19:
                level = 19
                ultra_mode = False
        elif memory_gb < 4.0:  # Less than 4GB memory
            if level > 20:
                level = 20

    # Detect CPU cores for thread optimization
    try:
        cpu_count = os.cpu_count() or 1
        if cpu_count > 1:
            threads = min(cpu_count, 16)  # Cap at 16 threads
    except Exception:
        threads = 0  # Fall back to auto-detect

    settings = CompressionSettings(
        level=level, threads=threads, long_mode=long_mode, ultra_mode=ultra_mode
    )

    logger.debug(f"Optimized compression settings for {file_size} bytes: {settings}")
    return settings


def estimate_compression_ratio(
    file_path: Union[str, Path], sample_size: int = 1024 * 1024
) -> float:
    """Estimate compression ratio by compressing a sample of the file.

    Args:
        file_path: Path to the file
        sample_size: Size of sample to test in bytes

    Returns:
        Estimated compression ratio (0.0 to 1.0)

    Raises:
        FileNotFoundError: If file doesn't exist
        CompressionError: If estimation fails
    """
    file_obj = Path(file_path)

    if not file_obj.exists():
        raise FileNotFoundError(f"File not found: {file_obj}")

    try:
        file_size = file_obj.stat().st_size
        actual_sample_size = min(sample_size, file_size)

        with open(file_obj, "rb") as f:
            sample_data = f.read(actual_sample_size)

        # Use fast compression for estimation
        compressor = ZstdCompressor(CompressionSettings(level=3, long_mode=False))
        compressed_data = compressor.compress_data(sample_data)

        ratio = len(compressed_data) / len(sample_data)
        logger.debug(f"Estimated compression ratio for {file_obj}: {ratio:.2f}")

        return ratio

    except Exception as e:
        raise CompressionError(f"Failed to estimate compression ratio: {e}") from e
