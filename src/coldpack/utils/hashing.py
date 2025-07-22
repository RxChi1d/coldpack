"""Dual hash system (SHA-256 + BLAKE3) for comprehensive file verification."""

import hashlib
from pathlib import Path
from typing import Callable, Optional, Union

import blake3
from loguru import logger

from ..config.constants import HASH_CHUNK_SIZE


class HashingError(Exception):
    """Base exception for hashing operations."""

    pass


class DualHasher:
    """Dual hasher that computes SHA-256 and BLAKE3 hashes simultaneously."""

    def __init__(self) -> None:
        """Initialize the dual hasher."""
        self.reset()

    def reset(self) -> None:
        """Reset hashers for new computation."""
        self.sha256_hasher = hashlib.sha256()
        self.blake3_hasher = blake3.blake3()
        self._bytes_processed = 0

    def update(self, data: bytes) -> None:
        """Update both hashers with data.

        Args:
            data: Data to hash
        """
        self.sha256_hasher.update(data)
        self.blake3_hasher.update(data)
        self._bytes_processed += len(data)

    def finalize(self) -> dict[str, str]:
        """Finalize hashing and return both hash values.

        Returns:
            Dictionary with SHA-256 and BLAKE3 hash values
        """
        return {
            "sha256": self.sha256_hasher.hexdigest(),
            "blake3": self.blake3_hasher.hexdigest(),
        }

    @property
    def bytes_processed(self) -> int:
        """Get number of bytes processed."""
        return self._bytes_processed


def compute_file_hashes(
    file_path: Union[str, Path],
    progress_callback: Optional[Callable[[float, int, int], None]] = None,
) -> dict[str, str]:
    """Compute SHA-256 and BLAKE3 hashes for a file using streaming.

    Args:
        file_path: Path to the file
        progress_callback: Optional callback for progress updates

    Returns:
        Dictionary with hash algorithm names as keys and hex digests as values

    Raises:
        FileNotFoundError: If file doesn't exist
        HashingError: If hashing fails
    """
    file_obj = Path(file_path)

    if not file_obj.exists():
        raise FileNotFoundError(f"File not found: {file_obj}")

    try:
        file_size = file_obj.stat().st_size
        hasher = DualHasher()

        logger.info(f"Computing dual hashes for {file_obj} ({file_size} bytes)")

        with open(file_obj, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break

                hasher.update(chunk)

                # Report progress if callback provided
                if progress_callback:
                    progress = (
                        hasher.bytes_processed / file_size if file_size > 0 else 1.0
                    )
                    progress_callback(progress, hasher.bytes_processed, file_size)

        hashes = hasher.finalize()

        logger.success(f"Computed hashes for {file_obj}:")
        logger.debug(f"  SHA-256: {hashes['sha256']}")
        logger.debug(f"  BLAKE3:  {hashes['blake3']}")

        return hashes

    except OSError as e:
        raise HashingError(f"Failed to read file for hashing: {e}") from e
    except Exception as e:
        raise HashingError(f"Hash computation failed: {e}") from e


def write_hash_file(
    file_path: Union[str, Path],
    hash_value: str,
    algorithm: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Write hash value to a hash file.

    Args:
        file_path: Path to the original file
        hash_value: Hash value in hex format
        algorithm: Hash algorithm name (sha256, blake3)
        output_dir: Optional directory to place the hash file (default: same as file_path)

    Returns:
        Path to the created hash file

    Raises:
        HashingError: If writing fails
    """
    file_obj = Path(file_path)

    if output_dir:
        # Place hash file in specified directory
        hash_file = output_dir / f"{file_obj.name}.{algorithm.lower()}"
    else:
        # Place hash file alongside the original file
        hash_file = file_obj.with_suffix(f"{file_obj.suffix}.{algorithm.lower()}")

    try:
        # Format: hash  filename (compatible with sha256sum, b3sum)
        content = f"{hash_value}  {file_obj.name}\n"

        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug(f"Created {algorithm.upper()} hash file: {hash_file}")
        return hash_file

    except OSError as e:
        raise HashingError(f"Failed to write {algorithm} hash file: {e}") from e


def generate_hash_files(
    file_path: Union[str, Path],
    hashes: dict[str, str],
    output_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """Generate hash files for all computed hashes.

    Args:
        file_path: Path to the original file
        hashes: Dictionary of hash algorithm names to hash values
        output_dir: Optional directory to place hash files (default: same as file_path)

    Returns:
        Dictionary mapping algorithm names to hash file paths

    Raises:
        HashingError: If hash file generation fails
    """
    hash_files = {}

    try:
        for algorithm, hash_value in hashes.items():
            hash_file_path = write_hash_file(
                file_path, hash_value, algorithm, output_dir=output_dir
            )
            hash_files[algorithm] = hash_file_path

        output_location = output_dir or Path(file_path).parent
        logger.success(
            f"Generated {len(hash_files)} hash files for {file_path} in {output_location}"
        )
        return hash_files

    except Exception as e:
        # Clean up any partially created hash files
        for hash_file in hash_files.values():
            try:
                if hash_file.exists():
                    hash_file.unlink()
            except OSError:
                pass

        raise HashingError(f"Failed to generate hash files: {e}") from e


class HashVerifier:
    """Verifier for hash files and integrity checking."""

    @staticmethod
    def read_hash_file(hash_file_path: Union[str, Path]) -> tuple[str, str]:
        """Read hash value and filename from a hash file.

        Args:
            hash_file_path: Path to the hash file

        Returns:
            Tuple of (hash_value, filename)

        Raises:
            FileNotFoundError: If hash file doesn't exist
            HashingError: If hash file format is invalid
        """
        hash_file = Path(hash_file_path)

        if not hash_file.exists():
            raise FileNotFoundError(f"Hash file not found: {hash_file}")

        try:
            with open(hash_file, encoding="utf-8") as f:
                line = f.readline().strip()

            # Parse format: hash  filename
            parts = line.split("  ", 1)
            if len(parts) != 2:
                raise HashingError(f"Invalid hash file format: {hash_file}")

            hash_value, filename = parts
            return hash_value.lower(), filename

        except OSError as e:
            raise HashingError(f"Failed to read hash file: {e}") from e

    @staticmethod
    def verify_file_hash(
        file_path: Union[str, Path], hash_file_path: Union[str, Path], algorithm: str
    ) -> bool:
        """Verify a file against its hash file.

        Args:
            file_path: Path to the file to verify
            hash_file_path: Path to the hash file
            algorithm: Hash algorithm name (sha256, blake3)

        Returns:
            True if verification passes

        Raises:
            HashingError: If verification fails or cannot be performed
        """
        try:
            # Read expected hash from file
            expected_hash, expected_filename = HashVerifier.read_hash_file(
                hash_file_path
            )

            # Check filename matches
            actual_filename = Path(file_path).name
            if actual_filename != expected_filename:
                logger.warning(
                    f"Filename mismatch: expected {expected_filename}, "
                    f"got {actual_filename}"
                )

            # Compute actual hash
            if algorithm.lower() == "sha256":
                actual_hash = compute_sha256_hash(file_path)
            elif algorithm.lower() == "blake3":
                actual_hash = compute_blake3_hash(file_path)
            else:
                raise HashingError(f"Unsupported hash algorithm: {algorithm}")

            # Compare hashes
            if actual_hash.lower() == expected_hash.lower():
                logger.success(
                    f"{algorithm.upper()} verification passed for {file_path}"
                )
                return True
            else:
                logger.error(f"{algorithm.upper()} verification failed for {file_path}")
                logger.error(f"Expected: {expected_hash}")
                logger.error(f"Actual:   {actual_hash}")
                return False

        except Exception as e:
            raise HashingError(f"{algorithm.upper()} verification failed: {e}") from e

    @staticmethod
    def verify_dual_hashes(
        file_path: Union[str, Path],
        sha256_file: Union[str, Path],
        blake3_file: Union[str, Path],
    ) -> bool:
        """Verify a file against both SHA-256 and BLAKE3 hash files.

        Args:
            file_path: Path to the file to verify
            sha256_file: Path to the SHA-256 hash file
            blake3_file: Path to the BLAKE3 hash file

        Returns:
            True if both verifications pass

        Raises:
            HashingError: If verification fails
        """
        logger.info(f"Verifying dual hashes for {file_path}")

        try:
            sha256_ok = HashVerifier.verify_file_hash(file_path, sha256_file, "sha256")
            blake3_ok = HashVerifier.verify_file_hash(file_path, blake3_file, "blake3")

            if sha256_ok and blake3_ok:
                logger.success(f"Dual hash verification passed for {file_path}")
                return True
            else:
                failed_algorithms = []
                if not sha256_ok:
                    failed_algorithms.append("SHA-256")
                if not blake3_ok:
                    failed_algorithms.append("BLAKE3")

                raise HashingError(
                    f"Hash verification failed for: {', '.join(failed_algorithms)}"
                )

        except Exception as e:
            raise HashingError(f"Dual hash verification failed: {e}") from e


def compute_sha256_hash(file_path: Union[str, Path]) -> str:
    """Compute SHA-256 hash for a file.

    Args:
        file_path: Path to the file

    Returns:
        SHA-256 hash in hex format

    Raises:
        FileNotFoundError: If file doesn't exist
        HashingError: If hashing fails
    """
    file_obj = Path(file_path)

    if not file_obj.exists():
        raise FileNotFoundError(f"File not found: {file_obj}")

    try:
        hasher = hashlib.sha256()

        with open(file_obj, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)

        return hasher.hexdigest()

    except Exception as e:
        raise HashingError(f"SHA-256 computation failed: {e}") from e


def compute_blake3_hash(file_path: Union[str, Path]) -> str:
    """Compute BLAKE3 hash for a file.

    Args:
        file_path: Path to the file

    Returns:
        BLAKE3 hash in hex format

    Raises:
        FileNotFoundError: If file doesn't exist
        HashingError: If hashing fails
    """
    file_obj = Path(file_path)

    if not file_obj.exists():
        raise FileNotFoundError(f"File not found: {file_obj}")

    try:
        hasher = blake3.blake3()

        with open(file_obj, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)

        return hasher.hexdigest()

    except Exception as e:
        raise HashingError(f"BLAKE3 computation failed: {e}") from e
