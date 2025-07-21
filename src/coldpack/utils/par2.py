"""PAR2 recovery file management and verification."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from ..config.constants import DEFAULT_PAR2_REDUNDANCY, PAR2_BLOCK_COUNT


class PAR2Error(Exception):
    """Base exception for PAR2 operations."""

    pass


class PAR2NotFoundError(PAR2Error):
    """Raised when par2 tool is not found."""

    pass


class PAR2Manager:
    """Manager for PAR2 recovery file operations."""

    def __init__(self, redundancy_percent: int = DEFAULT_PAR2_REDUNDANCY):
        """Initialize PAR2 manager.

        Args:
            redundancy_percent: Redundancy percentage (1-50)

        Raises:
            PAR2NotFoundError: If par2 tool is not available
        """
        if not (1 <= redundancy_percent <= 50):
            raise ValueError("Redundancy percentage must be between 1 and 50")

        self.redundancy_percent = redundancy_percent
        par2_cmd = self._find_par2_command()

        if not par2_cmd:
            raise PAR2NotFoundError(
                "par2 command not found. Please install par2cmdline or par2cmdline-turbo"
            )

        self.par2_cmd = par2_cmd

        logger.debug(
            f"PAR2Manager initialized with {redundancy_percent}% redundancy "
            f"using command: {self.par2_cmd}"
        )

    def _find_par2_command(self) -> Optional[str]:
        """Find available par2 command.

        Returns:
            Path to par2 command or None if not found
        """
        # Try different possible par2 command names
        candidates = ["par2", "par2cmdline", "par2create"]

        for cmd in candidates:
            if shutil.which(cmd):
                try:
                    # Test if the command works
                    result = subprocess.run(
                        [cmd, "--help"], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        logger.debug(f"Found working par2 command: {cmd}")
                        return cmd
                except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                    continue

        return None

    def create_recovery_files(self, file_path: Union[str, Path]) -> list[Path]:
        """Create PAR2 recovery files for a file.

        Args:
            file_path: Path to the file to protect

        Returns:
            List of created PAR2 recovery file paths

        Raises:
            FileNotFoundError: If input file doesn't exist
            PAR2Error: If PAR2 creation fails
        """
        file_obj = Path(file_path)

        if not file_obj.exists():
            raise FileNotFoundError(f"File not found: {file_obj}")

        # PAR2 base name - use relative path to ensure portability
        # PAR2 files store relative paths internally for cross-platform compatibility
        par2_base = (
            file_obj.name
        )  # Use filename as base (will be created in same directory)

        # Build par2 create command
        # Note: We use relative paths because:
        # 1. PAR2 stores paths internally in .par2 files
        # 2. Absolute paths make archives non-portable between systems
        # 3. We set cwd=work_dir below to ensure correct working directory
        cmd = [
            self.par2_cmd,
            "create",
            f"-r{self.redundancy_percent}",  # Redundancy percentage
            f"-n{PAR2_BLOCK_COUNT}",  # Number of recovery files
            "-q",  # Quiet mode
            par2_base,  # Base name for PAR2 files (relative)
            file_obj.name,  # File to protect (relative to working directory)
        ]

        try:
            logger.info(
                f"Creating PAR2 recovery files for {file_obj} "
                f"({self.redundancy_percent}% redundancy)"
            )

            # Change to file directory to avoid path issues
            original_cwd = Path.cwd()
            work_dir = file_obj.parent

            try:
                # Execute par2 create command
                result = subprocess.run(
                    cmd,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=3600,  # 1 hour timeout for large files
                )

                if result.returncode != 0:
                    raise PAR2Error(
                        f"PAR2 create failed (exit code {result.returncode}): "
                        f"{result.stderr}"
                    )

                # Find all created PAR2 files
                par2_files = self._find_par2_files(file_obj)

                if not par2_files:
                    raise PAR2Error("No PAR2 files were created")

                logger.success(f"Created {len(par2_files)} PAR2 recovery files")
                for par2_file in par2_files:
                    file_size = par2_file.stat().st_size
                    logger.debug(f"  {par2_file.name} ({file_size} bytes)")

                return par2_files

            finally:
                # Restore original working directory
                try:
                    original_cwd.exists() and original_cwd.is_dir()
                    # Only change back if original directory still exists
                    if original_cwd.exists():
                        pass  # subprocess.run already handles cwd context
                except OSError:
                    pass

        except subprocess.TimeoutExpired as e:
            raise PAR2Error(
                "PAR2 creation timed out (file too large or system too slow)"
            ) from e
        except subprocess.SubprocessError as e:
            raise PAR2Error(f"PAR2 command execution failed: {e}") from e
        except Exception as e:
            raise PAR2Error(f"PAR2 creation failed: {e}") from e

    def verify_recovery_files(self, par2_file: Union[str, Path]) -> bool:
        """Verify integrity using PAR2 recovery files.

        Args:
            par2_file: Path to main .par2 file

        Returns:
            True if verification passes

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            PAR2Error: If verification fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        cmd = [
            self.par2_cmd,
            "verify",
            "-q",  # Quiet mode
            par2_obj.name,  # Use relative path for consistency
        ]

        try:
            logger.info(f"Verifying PAR2 recovery files: {par2_obj}")

            result = subprocess.run(
                cmd,
                cwd=par2_obj.parent,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout
            )

            if result.returncode == 0:
                logger.success(f"PAR2 verification passed: {par2_obj}")
                return True
            else:
                logger.error(
                    f"PAR2 verification failed (exit code {result.returncode}): "
                    f"{result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired as e:
            raise PAR2Error("PAR2 verification timed out") from e
        except subprocess.SubprocessError as e:
            raise PAR2Error(f"PAR2 verification command failed: {e}") from e

    def repair_file(self, par2_file: Union[str, Path]) -> bool:
        """Attempt to repair a file using PAR2 recovery data.

        Args:
            par2_file: Path to main .par2 file

        Returns:
            True if repair was successful

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            PAR2Error: If repair fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        cmd = [
            self.par2_cmd,
            "repair",
            "-q",  # Quiet mode
            par2_obj.name,  # Use relative path for consistency
        ]

        try:
            logger.info(f"Attempting PAR2 repair: {par2_obj}")

            result = subprocess.run(
                cmd,
                cwd=par2_obj.parent,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.success(f"PAR2 repair completed successfully: {par2_obj}")
                return True
            else:
                logger.error(
                    f"PAR2 repair failed (exit code {result.returncode}): "
                    f"{result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired as e:
            raise PAR2Error("PAR2 repair timed out") from e
        except subprocess.SubprocessError as e:
            raise PAR2Error(f"PAR2 repair command failed: {e}") from e

    def _find_par2_files(self, original_file: Path) -> list[Path]:
        """Find all PAR2 files created for an original file.

        Args:
            original_file: Path to the original file

        Returns:
            List of PAR2 file paths
        """
        par2_files = []
        base_pattern = original_file.name

        # Look for PAR2 files in the same directory
        for file_path in original_file.parent.iterdir():
            if file_path.name.startswith(base_pattern) and file_path.suffix == ".par2":
                par2_files.append(file_path)

        # Sort to ensure consistent ordering
        return sorted(par2_files)

    def get_recovery_info(self, par2_file: Union[str, Path]) -> dict:
        """Get information about PAR2 recovery files.

        Args:
            par2_file: Path to main .par2 file

        Returns:
            Dictionary with recovery information

        Raises:
            FileNotFoundError: If PAR2 file doesn't exist
            PAR2Error: If info retrieval fails
        """
        par2_obj = Path(par2_file)

        if not par2_obj.exists():
            raise FileNotFoundError(f"PAR2 file not found: {par2_obj}")

        # Find all related PAR2 files
        original_file_pattern = par2_obj.name.replace(".par2", "")
        all_par2_files = self._find_par2_files(par2_obj.parent / original_file_pattern)

        total_size = sum(f.stat().st_size for f in all_par2_files)

        return {
            "par2_files": [str(f) for f in all_par2_files],
            "file_count": len(all_par2_files),
            "total_size": total_size,
            "redundancy_percent": self.redundancy_percent,
            "main_par2_file": str(par2_obj),
        }


def check_par2_availability() -> bool:
    """Check if PAR2 tools are available on the system.

    Returns:
        True if PAR2 is available
    """
    try:
        PAR2Manager()
        return True
    except PAR2NotFoundError:
        return False


def get_par2_version() -> Optional[str]:
    """Get the version of the installed PAR2 tool.

    Returns:
        Version string or None if not available
    """
    try:
        manager = PAR2Manager()

        result = subprocess.run(
            [manager.par2_cmd, "--version"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            # Extract version from output
            lines = result.stdout.split("\n")
            for line in lines:
                if "version" in line.lower():
                    return line.strip()

        return None

    except Exception:
        return None


def install_par2_instructions() -> str:
    """Get installation instructions for PAR2 based on the current platform.

    Returns:
        Installation instructions string
    """
    if sys.platform.startswith("darwin"):  # macOS
        return (
            "Install PAR2 on macOS:\n"
            "  brew install par2cmdline\n"
            "  or\n"
            "  brew install par2cmdline-turbo"
        )
    elif sys.platform.startswith("linux"):  # Linux
        return (
            "Install PAR2 on Linux:\n"
            "  Ubuntu/Debian: sudo apt install par2cmdline\n"
            "  CentOS/RHEL: sudo yum install par2cmdline\n"
            "  Arch: sudo pacman -S par2cmdline\n"
            "  or install par2cmdline-turbo for better performance"
        )
    elif sys.platform.startswith("win"):  # Windows
        return (
            "Install PAR2 on Windows:\n"
            "  Download from: https://github.com/Parchive/par2cmdline/releases\n"
            "  or use chocolatey: choco install par2cmdline\n"
            "  or use winget: winget install par2cmdline"
        )
    else:
        return (
            "Install PAR2 for your platform:\n"
            "  Visit: https://github.com/Parchive/par2cmdline\n"
            "  or: https://github.com/animetosho/par2cmdline-turbo"
        )
