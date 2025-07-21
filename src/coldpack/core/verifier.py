"""5-layer verification system for comprehensive archive integrity checking."""

import subprocess
import tarfile
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..utils.compression import ZstdDecompressor
from ..utils.hashing import HashVerifier


class VerificationError(Exception):
    """Base exception for verification operations."""

    pass


class VerificationResult:
    """Result of a verification operation."""

    def __init__(
        self,
        layer: str,
        success: bool,
        message: str = "",
        details: Optional[dict] = None,
    ):
        """Initialize verification result.

        Args:
            layer: Verification layer name
            success: Whether verification passed
            message: Result message
            details: Additional details dictionary
        """
        self.layer = layer
        self.success = success
        self.message = message
        self.details = details or {}
        self.timestamp = None

    def __str__(self) -> str:
        """String representation of the result."""
        status = "PASS" if self.success else "FAIL"
        return f"[{self.layer}] {status}: {self.message}"


class ArchiveVerifier:
    """Comprehensive archive verifier implementing 5-layer verification."""

    def __init__(self) -> None:
        """Initialize the archive verifier."""
        self.decompressor = ZstdDecompressor()
        self.hash_verifier = HashVerifier()
        self.par2_manager: Optional[Any] = None  # Initialized when needed
        logger.debug("ArchiveVerifier initialized")

    def verify_complete(
        self,
        archive_path: Union[str, Path],
        hash_files: Optional[dict[str, Path]] = None,
        par2_file: Optional[Path] = None,
        par2_redundancy: int = 10,
    ) -> list[VerificationResult]:
        """Perform complete 5-layer verification.

        Args:
            archive_path: Path to the tar.zst archive
            hash_files: Dictionary of algorithm names to hash file paths
            par2_file: Path to PAR2 recovery file
            par2_redundancy: PAR2 redundancy percentage for proper verification

        Returns:
            List of verification results for each layer

        Raises:
            FileNotFoundError: If archive doesn't exist
            VerificationError: If verification setup fails
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            raise FileNotFoundError(f"Archive not found: {archive_obj}")

        logger.info(f"Starting 5-layer verification for: {archive_obj}")

        results = []

        # Layer 1: Zstd integrity verification
        try:
            result = self.verify_zstd_integrity(archive_obj)
            results.append(result)
            if not result.success:
                logger.error("Zstd verification failed, skipping remaining layers")
                return results
        except Exception as e:
            results.append(
                VerificationResult("zstd_integrity", False, f"Verification error: {e}")
            )
            return results

        # Layer 2: TAR header verification
        try:
            result = self.verify_tar_structure(archive_obj)
            results.append(result)
            if not result.success:
                logger.warning(
                    "TAR verification failed, continuing with remaining layers"
                )
        except Exception as e:
            results.append(
                VerificationResult("tar_header", False, f"Verification error: {e}")
            )

        # Layer 3 & 4: Hash verification (SHA-256 + BLAKE3)
        if hash_files:
            try:
                result = self.verify_hash_files(archive_obj, hash_files)
                results.append(result)
            except Exception as e:
                results.append(
                    VerificationResult(
                        "dual_hash", False, f"Hash verification error: {e}"
                    )
                )
        else:
            results.append(
                VerificationResult("dual_hash", False, "Hash files not provided")
            )

        # Layer 5: PAR2 recovery verification
        if par2_file:
            try:
                result = self.verify_par2_recovery(par2_file, par2_redundancy)
                results.append(result)
            except Exception as e:
                results.append(
                    VerificationResult(
                        "par2_recovery", False, f"PAR2 verification error: {e}"
                    )
                )
        else:
            results.append(
                VerificationResult("par2_recovery", False, "PAR2 file not provided")
            )

        # Summary
        passed_layers = sum(1 for r in results if r.success)
        total_layers = len(results)

        logger.info(
            f"Verification complete: {passed_layers}/{total_layers} layers passed"
        )

        return results

    def verify_zstd_integrity(
        self, archive_path: Union[str, Path]
    ) -> VerificationResult:
        """Verify Zstd compression integrity.

        Args:
            archive_path: Path to the zst archive

        Returns:
            Verification result
        """
        archive_obj = Path(archive_path)

        try:
            logger.debug(f"Verifying Zstd integrity: {archive_obj}")

            # Use zstd decompressor to test integrity
            is_valid = self.decompressor.test_integrity(archive_obj)

            if is_valid:
                return VerificationResult(
                    "zstd_integrity", True, "Zstd integrity check passed"
                )
            else:
                return VerificationResult(
                    "zstd_integrity", False, "Zstd integrity check failed"
                )

        except Exception as e:
            return VerificationResult(
                "zstd_integrity", False, f"Zstd verification error: {e}"
            )

    def verify_tar_structure(
        self, archive_path: Union[str, Path]
    ) -> VerificationResult:
        """Verify TAR structure after decompression.

        Args:
            archive_path: Path to the tar.zst archive

        Returns:
            Verification result
        """
        archive_obj = Path(archive_path)

        try:
            logger.debug(f"Verifying TAR structure: {archive_obj}")

            # Method 1: Use tarfile with zstd decompression stream
            try:
                if self.decompressor._context is None:
                    raise ValueError("Decompressor context not initialized")

                with (
                    open(archive_obj, "rb") as f,
                    self.decompressor._context.stream_reader(f) as reader,
                    tarfile.open(fileobj=reader, mode="r|") as tar,
                ):
                    # Try to read tar info - this will fail if structure is invalid
                    members = []
                    for member in tar:
                        members.append(member.name)
                        # Limit check to avoid memory issues
                        if len(members) > 1000:
                            break

                return VerificationResult(
                    "tar_header",
                    True,
                    f"TAR structure valid ({len(members)} entries checked)",
                    {"entries_checked": len(members)},
                )

            except Exception:
                # Method 2: Use external tar command as fallback
                return self._verify_tar_with_command(archive_obj)

        except Exception as e:
            return VerificationResult(
                "tar_header", False, f"TAR verification error: {e}"
            )

    def _verify_tar_with_command(self, archive_path: Path) -> VerificationResult:
        """Verify TAR structure using external tar command.

        Args:
            archive_path: Path to the tar.zst archive

        Returns:
            Verification result
        """
        try:
            # Use zstd + tar pipeline for verification
            cmd = f"zstd -dc '{archive_path}' | tar -tf - > /dev/null"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                return VerificationResult(
                    "tar_header", True, "TAR structure valid (external verification)"
                )
            else:
                return VerificationResult(
                    "tar_header", False, f"TAR verification failed: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            return VerificationResult("tar_header", False, "TAR verification timed out")
        except Exception as e:
            return VerificationResult(
                "tar_header", False, f"TAR command verification error: {e}"
            )

    def verify_hash_files(
        self, archive_path: Union[str, Path], hash_files: dict[str, Path]
    ) -> VerificationResult:
        """Verify hash files against the archive.

        Args:
            archive_path: Path to the archive
            hash_files: Dictionary of algorithm names to hash file paths

        Returns:
            Verification result
        """
        archive_obj = Path(archive_path)

        try:
            logger.debug(f"Verifying hash files for: {archive_obj}")

            verified_algorithms = []
            failed_algorithms = []

            for algorithm, hash_file_path in hash_files.items():
                try:
                    success = self.hash_verifier.verify_file_hash(
                        archive_obj, hash_file_path, algorithm
                    )

                    if success:
                        verified_algorithms.append(algorithm.upper())
                    else:
                        failed_algorithms.append(algorithm.upper())

                except Exception as e:
                    logger.error(f"{algorithm.upper()} verification failed: {e}")
                    failed_algorithms.append(algorithm.upper())

            if failed_algorithms:
                return VerificationResult(
                    "dual_hash",
                    False,
                    f"Hash verification failed for: {', '.join(failed_algorithms)}",
                    {"verified": verified_algorithms, "failed": failed_algorithms},
                )
            else:
                return VerificationResult(
                    "dual_hash",
                    True,
                    f"Hash verification passed for: {', '.join(verified_algorithms)}",
                    {"verified": verified_algorithms},
                )

        except Exception as e:
            return VerificationResult(
                "dual_hash", False, f"Hash verification error: {e}"
            )

    def verify_par2_recovery(
        self, par2_file: Union[str, Path], par2_redundancy: int = 10
    ) -> VerificationResult:
        """Verify PAR2 recovery files.

        Args:
            par2_file: Path to the main PAR2 file
            par2_redundancy: PAR2 redundancy percentage for proper initialization

        Returns:
            Verification result
        """
        par2_obj = Path(par2_file)

        try:
            logger.debug(f"Verifying PAR2 recovery: {par2_obj}")

            # Always create a new PAR2Manager with the correct redundancy
            from ..utils.par2 import PAR2Manager

            self.par2_manager = PAR2Manager(par2_redundancy)

            # Perform PAR2 verification
            assert self.par2_manager is not None
            success = self.par2_manager.verify_recovery_files(par2_obj)

            if success:
                return VerificationResult(
                    "par2_recovery", True, "PAR2 verification passed"
                )
            else:
                return VerificationResult(
                    "par2_recovery", False, "PAR2 verification failed"
                )

        except Exception as e:
            return VerificationResult(
                "par2_recovery", False, f"PAR2 verification error: {e}"
            )

    def get_verification_summary(self, results: list[VerificationResult]) -> dict:
        """Get summary of verification results.

        Args:
            results: List of verification results

        Returns:
            Summary dictionary
        """
        total_layers = len(results)
        passed_layers = sum(1 for r in results if r.success)
        failed_layers = total_layers - passed_layers

        success_rate = (passed_layers / total_layers * 100) if total_layers > 0 else 0

        # Group results by status
        passed_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        return {
            "total_layers": total_layers,
            "passed_layers": passed_layers,
            "failed_layers": failed_layers,
            "success_rate": success_rate,
            "overall_success": failed_layers == 0,
            "passed": [r.layer for r in passed_results],
            "failed": [r.layer for r in failed_results],
            "details": {
                r.layer: {"message": r.message, "details": r.details} for r in results
            },
        }

    def verify_quick(self, archive_path: Union[str, Path]) -> bool:
        """Perform quick verification (zstd integrity only).

        Args:
            archive_path: Path to the archive

        Returns:
            True if quick verification passes
        """
        try:
            result = self.verify_zstd_integrity(archive_path)
            return result.success
        except Exception:
            return False


def verify_archive(
    archive_path: Union[str, Path],
    hash_files: Optional[dict[str, Path]] = None,
    par2_file: Optional[Path] = None,
    par2_redundancy: int = 10,
) -> list[VerificationResult]:
    """Convenience function for complete archive verification.

    Args:
        archive_path: Path to the archive
        hash_files: Dictionary of algorithm names to hash file paths
        par2_file: Path to PAR2 recovery file
        par2_redundancy: PAR2 redundancy percentage

    Returns:
        List of verification results
    """
    verifier = ArchiveVerifier()
    return verifier.verify_complete(
        archive_path, hash_files, par2_file, par2_redundancy
    )


def quick_verify(archive_path: Union[str, Path]) -> bool:
    """Convenience function for quick archive verification.

    Args:
        archive_path: Path to the archive

    Returns:
        True if verification passes
    """
    verifier = ArchiveVerifier()
    return verifier.verify_quick(archive_path)
