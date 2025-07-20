"""PAR2 repair functionality for archive recovery operations."""

from pathlib import Path
from typing import Optional, Union

from loguru import logger

from ..utils.par2 import PAR2Error, PAR2Manager, PAR2NotFoundError


class RepairError(Exception):
    """Base exception for repair operations."""

    pass


class RepairResult:
    """Result of a repair operation."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        repaired_files: Optional[list[str]] = None,
        error_details: Optional[str] = None,
    ):
        """Initialize repair result.

        Args:
            success: Whether repair was successful
            message: Result message
            repaired_files: List of files that were repaired
            error_details: Detailed error information
        """
        self.success = success
        self.message = message
        self.repaired_files = repaired_files or []
        self.error_details = error_details

    def __str__(self) -> str:
        """String representation of the result."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"Repair {status}: {self.message}"


class ArchiveRepairer:
    """Archive repairer using PAR2 recovery files."""

    def __init__(self, redundancy_percent: int = 10):
        """Initialize the archive repairer.

        Args:
            redundancy_percent: PAR2 redundancy percentage for new archives

        Raises:
            RepairError: If PAR2 tools are not available
        """
        try:
            self.par2_manager = PAR2Manager(redundancy_percent)
            logger.debug(
                f"ArchiveRepairer initialized with {redundancy_percent}% redundancy"
            )
        except PAR2NotFoundError as e:
            raise RepairError(f"PAR2 tools not available: {e}") from e

    def repair_archive(self, par2_file: Union[str, Path]) -> RepairResult:
        """Attempt to repair an archive using PAR2 recovery files.

        Args:
            par2_file: Path to the main PAR2 recovery file

        Returns:
            Repair result object

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            RepairError: If repair setup fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        # Extract original file name from PAR2 file
        original_file = self._get_original_file_from_par2(par2_obj)

        logger.info(f"Attempting repair for: {original_file} using {par2_obj}")

        try:
            # First, verify current state
            verification_result = self._verify_before_repair(par2_obj, original_file)

            if verification_result["needs_repair"]:
                # Perform repair
                success = self.par2_manager.repair_file(par2_obj)

                if success:
                    # Verify repair was successful
                    post_repair_verification = self._verify_after_repair(
                        par2_obj, original_file
                    )

                    if post_repair_verification["success"]:
                        return RepairResult(
                            success=True,
                            message=f"Successfully repaired {original_file}",
                            repaired_files=[str(original_file)],
                        )
                    else:
                        return RepairResult(
                            success=False,
                            message="Repair completed but verification still fails",
                            error_details=post_repair_verification.get("error"),
                        )
                else:
                    return RepairResult(
                        success=False,
                        message="PAR2 repair operation failed",
                        error_details="PAR2 repair command returned failure status",
                    )
            else:
                return RepairResult(
                    success=True,
                    message="No repair needed - archive is already valid",
                    repaired_files=[],
                )

        except Exception as e:
            logger.error(f"Repair failed: {e}")
            return RepairResult(
                success=False, message=f"Repair failed: {e}", error_details=str(e)
            )

    def check_repair_capability(self, par2_file: Union[str, Path]) -> dict:
        """Check if an archive can be repaired and what damage exists.

        Args:
            par2_file: Path to the main PAR2 recovery file

        Returns:
            Dictionary with repair capability information

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            RepairError: If check fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        try:
            logger.debug(f"Checking repair capability for: {par2_obj}")

            # Get PAR2 recovery info
            recovery_info = self.par2_manager.get_recovery_info(par2_obj)

            # Get original file info
            original_file = self._get_original_file_from_par2(par2_obj)

            # Check current file state
            file_exists = original_file.exists() if original_file else False

            # Verify current state
            verification_result = self._verify_before_repair(par2_obj, original_file)

            return {
                "original_file": str(original_file) if original_file else None,
                "file_exists": file_exists,
                "needs_repair": verification_result["needs_repair"],
                "can_repair": True,  # Assume we can repair if PAR2 files exist
                "par2_info": recovery_info,
                "verification_status": verification_result,
                "redundancy_available": f"{recovery_info.get('redundancy_percent', 0)}%",
            }

        except Exception as e:
            raise RepairError(f"Failed to check repair capability: {e}") from e

    def create_recovery_files(self, file_path: Union[str, Path]) -> list[Path]:
        """Create PAR2 recovery files for a file.

        Args:
            file_path: Path to the file to protect

        Returns:
            List of created PAR2 file paths

        Raises:
            FileNotFoundError: If file doesn't exist
            RepairError: If creation fails
        """
        file_obj = Path(file_path)

        if not file_obj.exists():
            raise FileNotFoundError(f"File not found: {file_obj}")

        try:
            logger.info(f"Creating PAR2 recovery files for: {file_obj}")

            par2_files = self.par2_manager.create_recovery_files(file_obj)

            logger.success(f"Created {len(par2_files)} PAR2 recovery files")
            return par2_files

        except PAR2Error as e:
            raise RepairError(f"PAR2 recovery file creation failed: {e}") from e

    def verify_recovery_files(self, par2_file: Union[str, Path]) -> bool:
        """Verify PAR2 recovery files without repairing.

        Args:
            par2_file: Path to the main PAR2 recovery file

        Returns:
            True if verification passes

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            RepairError: If verification fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        try:
            return self.par2_manager.verify_recovery_files(par2_obj)
        except PAR2Error as e:
            raise RepairError(f"PAR2 verification failed: {e}") from e

    def _get_original_file_from_par2(self, par2_file: Path) -> Optional[Path]:
        """Extract original file path from PAR2 file name.

        Args:
            par2_file: Path to PAR2 file

        Returns:
            Path to original file or None if cannot be determined
        """
        try:
            # PAR2 files are typically named: original_file.par2
            par2_name = par2_file.name

            if par2_name.endswith(".par2"):
                original_name = par2_name[:-5]  # Remove .par2 extension
                original_file = par2_file.parent / original_name
                return original_file

            return None

        except Exception:
            return None

    def _verify_before_repair(
        self, par2_file: Path, original_file: Optional[Path]
    ) -> dict:
        """Verify archive state before attempting repair.

        Args:
            par2_file: Path to PAR2 file
            original_file: Path to original file

        Returns:
            Dictionary with verification status
        """
        try:
            # Check if original file exists
            if not original_file or not original_file.exists():
                return {
                    "needs_repair": True,
                    "reason": "Original file is missing",
                    "file_missing": True,
                }

            # Try PAR2 verification
            try:
                verification_passed = self.par2_manager.verify_recovery_files(par2_file)

                return {
                    "needs_repair": not verification_passed,
                    "reason": "File integrity check failed"
                    if not verification_passed
                    else "File is valid",
                    "file_missing": False,
                    "verification_passed": verification_passed,
                }

            except Exception as e:
                return {
                    "needs_repair": True,
                    "reason": f"Verification failed: {e}",
                    "file_missing": False,
                    "verification_error": str(e),
                }

        except Exception as e:
            return {
                "needs_repair": True,
                "reason": f"Pre-repair check failed: {e}",
                "error": str(e),
            }

    def _verify_after_repair(
        self, par2_file: Path, original_file: Optional[Path]
    ) -> dict:
        """Verify archive state after repair.

        Args:
            par2_file: Path to PAR2 file
            original_file: Path to original file

        Returns:
            Dictionary with verification status
        """
        try:
            # Check if file now exists (in case it was missing)
            if not original_file or not original_file.exists():
                return {"success": False, "reason": "File still missing after repair"}

            # Verify using PAR2
            verification_passed = self.par2_manager.verify_recovery_files(par2_file)

            return {
                "success": verification_passed,
                "reason": "Repair successful"
                if verification_passed
                else "Repair incomplete",
                "verification_passed": verification_passed,
            }

        except Exception as e:
            return {
                "success": False,
                "reason": f"Post-repair verification failed: {e}",
                "error": str(e),
            }


def repair_archive(par2_file: Union[str, Path]) -> RepairResult:
    """Convenience function to repair an archive.

    Args:
        par2_file: Path to PAR2 recovery file

    Returns:
        Repair result

    Raises:
        RepairError: If repair cannot be performed
    """
    repairer = ArchiveRepairer()
    return repairer.repair_archive(par2_file)


def check_repair_capability(par2_file: Union[str, Path]) -> dict:
    """Convenience function to check repair capability.

    Args:
        par2_file: Path to PAR2 recovery file

    Returns:
        Repair capability information

    Raises:
        RepairError: If check cannot be performed
    """
    repairer = ArchiveRepairer()
    return repairer.check_repair_capability(par2_file)


def create_recovery_files(
    file_path: Union[str, Path], redundancy_percent: int = 10
) -> list[Path]:
    """Convenience function to create PAR2 recovery files.

    Args:
        file_path: Path to the file to protect
        redundancy_percent: PAR2 redundancy percentage

    Returns:
        List of created PAR2 file paths

    Raises:
        RepairError: If creation fails
    """
    repairer = ArchiveRepairer(redundancy_percent)
    return repairer.create_recovery_files(file_path)
