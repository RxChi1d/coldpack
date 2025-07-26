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
            f"PAR2Manager initialized: {redundancy_percent}% redundancy, command: {self.par2_cmd}"
        )

    def _find_par2_command(self) -> Optional[str]:
        """Find available par2 command.

        Returns:
            Path to par2 command or None if not found
        """
        # Try different possible par2 command names
        # Note: par2cmdline-turbo package installs 'par2' executable
        candidates = ["par2", "par2cmdline", "par2create", "par2turbo"]

        # First try to find commands in system PATH
        for cmd in candidates:
            if shutil.which(cmd):
                try:
                    # Test if the command works
                    result = subprocess.run(
                        [cmd, "--help"], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        logger.debug(f"Found PAR2 command in PATH: {cmd}")
                        return cmd
                except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                    continue

        # If not found in PATH, try common installation locations
        import sys
        from pathlib import Path

        # Additional search paths for different installation methods
        additional_paths = []

        # Check if we're in a virtual environment or uv tool installation
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            # We're in a virtual environment (including uv tool environments)
            venv_bin = Path(sys.prefix) / "bin"
            if venv_bin.exists():
                additional_paths.append(venv_bin)

            # For Windows virtual environments
            venv_scripts = Path(sys.prefix) / "Scripts"
            if venv_scripts.exists():
                additional_paths.append(venv_scripts)

        # For uv tool installations, also check the executable's directory
        try:
            import coldpack

            # Get coldpack package location
            coldpack_module_path = Path(coldpack.__file__).parent

            # Check multiple possible locations relative to coldpack installation
            possible_locations = [
                # For development installations (pip install -e .)
                coldpack_module_path.parent.parent / "bin",
                coldpack_module_path.parent.parent / "Scripts",  # Windows
                # For wheel/site-packages installations
                coldpack_module_path.parent / "bin",
                coldpack_module_path.parent / "Scripts",  # Windows
                # For uv tool installs - check if we're in a uv-managed environment
                Path(sys.executable).parent,  # Same directory as Python executable
                # Check if we're in site-packages and look for bundled tools
                coldpack_module_path / "bin",
                coldpack_module_path / "tools",
            ]

            additional_paths.extend(p for p in possible_locations if p.exists())
        except Exception:
            # If anything fails, just continue with other paths
            pass

        # Check executable's parent directory (for bundled installations)
        exe_path = Path(sys.executable).parent
        additional_paths.append(exe_path)

        # macOS Homebrew paths
        if sys.platform.startswith("darwin"):
            homebrew_paths = [
                Path("/opt/homebrew/bin"),  # Apple Silicon
                Path("/usr/local/bin"),  # Intel
            ]
            additional_paths.extend(p for p in homebrew_paths if p.exists())

        # Linux package manager paths
        elif sys.platform.startswith("linux"):
            linux_paths = [
                Path("/usr/bin"),
                Path("/usr/local/bin"),
            ]
            additional_paths.extend(p for p in linux_paths if p.exists())

        # Windows paths
        elif sys.platform.startswith("win"):
            # Common Windows installation paths
            windows_paths = [
                Path("C:/Program Files/par2cmdline"),
                Path("C:/Program Files (x86)/par2cmdline"),
            ]
            additional_paths.extend(p for p in windows_paths if p.exists())

            # For Windows, also check common user installation locations
            import os

            if "USERPROFILE" in os.environ:
                user_profile = Path(os.environ["USERPROFILE"])
                user_paths = [
                    user_profile
                    / "AppData"
                    / "Local"
                    / "uv"
                    / "tools"
                    / "coldpack"
                    / "Scripts",
                    user_profile / "scoop" / "apps" / "par2cmdline" / "current",
                    user_profile / "scoop" / "shims",
                ]
                additional_paths.extend(p for p in user_paths if p.exists())

        # Try candidates in additional search paths
        for search_path in additional_paths:
            for cmd in candidates:
                full_path = search_path / cmd
                if sys.platform.startswith("win"):
                    # Also try with .exe extension on Windows
                    full_path_exe = search_path / f"{cmd}.exe"
                    for candidate_path in [full_path, full_path_exe]:
                        if candidate_path.exists() and candidate_path.is_file():
                            try:
                                result = subprocess.run(
                                    [str(candidate_path), "--help"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if result.returncode == 0:
                                    logger.debug(
                                        f"Found PAR2 command at: {candidate_path}"
                                    )
                                    return str(candidate_path)
                            except (
                                subprocess.TimeoutExpired,
                                subprocess.SubprocessError,
                            ):
                                continue
                else:
                    if full_path.exists() and full_path.is_file():
                        try:
                            result = subprocess.run(
                                [str(full_path), "--help"],
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            if result.returncode == 0:
                                logger.debug(f"Found PAR2 command at: {full_path}")
                                return str(full_path)
                        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                            continue

        # Debug information about search paths
        logger.debug(f"Searched for PAR2 commands: {candidates}")
        logger.debug(
            f"Additional search paths checked: {[str(p) for p in additional_paths]}"
        )
        logger.debug("No PAR2 command found in PATH or common locations")
        return None

    def create_recovery_files(
        self, file_path: Union[str, Path], output_dir: Optional[Path] = None
    ) -> list[Path]:
        """Create PAR2 recovery files for a file.

        Args:
            file_path: Path to the file to protect
            output_dir: Optional directory to place PAR2 files (default: same as file_path)

        Returns:
            List of created PAR2 recovery file paths

        Raises:
            FileNotFoundError: If input file doesn't exist
            PAR2Error: If PAR2 creation fails
        """
        file_obj = Path(file_path)

        if not file_obj.exists():
            raise FileNotFoundError(f"File not found: {file_obj}")

        if output_dir:
            # Use PAR2 -B (basepath) parameter to create files directly in output directory
            # This avoids the need to create files and then move them
            output_dir.mkdir(parents=True, exist_ok=True)

            # The basepath should be the directory containing the file to protect
            basepath = str(file_obj.parent.absolute())

            # PAR2 files will be created in output_dir, with basepath-relative file references
            par2_base = file_obj.name  # Base name for PAR2 files
            target_file = file_obj.name  # File to protect (relative to basepath)

            # Build par2 create command with -B parameter
            # Format: par2 create -B<basepath> -r<redundancy> -n<count> -q <relative_par2_path> <target_file>
            # Example: par2 create -B"/base/path" -r10 -n1 -q metadata/file.par2 file.ext
            relative_output_path = output_dir.relative_to(
                file_obj.parent
            )  # e.g., "metadata"
            cmd = [
                self.par2_cmd,
                "create",
                f"-B{basepath}",  # Base path for file references
                f"-r{self.redundancy_percent}",  # Redundancy percentage
                f"-n{PAR2_BLOCK_COUNT}",  # Number of recovery files
                "-q",  # Quiet mode
                str(relative_output_path / par2_base),  # Relative path for PAR2 files
                target_file,  # File to protect (relative to working directory)
            ]

            work_dir = file_obj.parent  # Run from directory containing the target file
        else:
            # Standard creation in same directory as protected file
            work_dir = file_obj.parent
            par2_base = file_obj.name  # Base name for PAR2 files
            target_file = file_obj.name  # File to protect (same directory)

            # Build standard par2 create command
            cmd = [
                self.par2_cmd,
                "create",
                f"-r{self.redundancy_percent}",  # Redundancy percentage
                f"-n{PAR2_BLOCK_COUNT}",  # Number of recovery files
                "-q",  # Quiet mode
                par2_base,  # Base name for PAR2 files
                target_file,  # File to protect (relative path)
            ]

        try:
            logger.debug(
                f"Creating PAR2 recovery files ({self.redundancy_percent}% redundancy)"
            )

            # Debug: Log the command and working directory
            logger.debug(f"PAR2 command: {' '.join(cmd)}")
            logger.debug(f"Working directory: {work_dir}")
            logger.debug(
                f"Target file exists: {(work_dir / target_file).exists() if work_dir else False}"
            )

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

            # Find all created PAR2 files in the appropriate location
            if output_dir:
                par2_files = self._find_par2_files_in_dir(file_obj, output_dir)
            else:
                par2_files = self._find_par2_files(file_obj)

            if not par2_files:
                raise PAR2Error("No PAR2 files were created")

            logger.debug(f"Generated {len(par2_files)} PAR2 recovery files")
            for par2_file in par2_files:
                file_size = par2_file.stat().st_size
                logger.debug(f"  {par2_file.name} ({file_size} bytes)")

            return par2_files

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

        # For PAR2 files in metadata directory, use -B parameter for verification
        if par2_obj.parent.name == "metadata":
            # Use the directory containing the protected files (7z location) as basepath
            basepath = str(par2_obj.parent.parent.absolute())
            work_dir = par2_obj.parent  # Run from metadata directory
            par2_rel_path = par2_obj.name  # PAR2 file name in metadata directory

            cmd = [
                self.par2_cmd,
                "verify",
                f"-B{basepath}",  # Use the 7z directory as basepath
                "-q",  # Quiet mode
                par2_rel_path,
            ]
        else:
            # Standard case - PAR2 files in same directory as protected files
            work_dir = par2_obj.parent
            par2_rel_path = par2_obj.name

            cmd = [
                self.par2_cmd,
                "verify",
                "-q",  # Quiet mode
                par2_rel_path,  # PAR2 file name
            ]

        try:
            logger.debug(f"PAR2 verification: {par2_rel_path} from {work_dir}")
            if par2_obj.parent.name == "metadata":
                logger.debug(f"Using basepath: {basepath}")

            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout
            )

            if result.returncode == 0:
                logger.success("PAR2 integrity check passed")
                return True
            else:
                logger.error(
                    f"PAR2 verification failed (exit code {result.returncode}): {result.stderr}"
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

        # For PAR2 files in metadata directory, use -B parameter for repair
        if par2_obj.parent.name == "metadata":
            # Use the directory containing the protected files (7z location) as basepath
            basepath = str(par2_obj.parent.parent.absolute())
            work_dir = par2_obj.parent  # Run from metadata directory

            cmd = [
                self.par2_cmd,
                "repair",
                f"-B{basepath}",  # Use the 7z directory as basepath
                "-q",  # Quiet mode
                par2_obj.name,  # PAR2 file name in metadata directory
            ]
        else:
            # Standard case - PAR2 files in same directory as protected files
            work_dir = par2_obj.parent
            par2_rel_path = par2_obj.name

            cmd = [
                self.par2_cmd,
                "repair",
                "-q",  # Quiet mode
                par2_rel_path,  # PAR2 file name
            ]

        try:
            logger.info(f"Attempting PAR2 repair using: {par2_obj.name}")

            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.success("PAR2 repair completed successfully")
                return True
            else:
                logger.error(
                    f"PAR2 repair failed (exit code {result.returncode}): {result.stderr}"
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

    def _find_par2_files_in_dir(
        self, original_file: Path, search_dir: Path
    ) -> list[Path]:
        """Find all PAR2 files created for an original file in a specific directory.

        Args:
            original_file: Path to the original file
            search_dir: Directory to search for PAR2 files

        Returns:
            List of PAR2 file paths
        """
        par2_files = []
        base_pattern = original_file.name

        # Look for PAR2 files in the specified directory
        for file_path in search_dir.iterdir():
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
    base_msg = (
        "Note: coldpack includes par2cmdline-turbo as a dependency, but the executable may not be in PATH.\n"
        "If you installed coldpack with 'uv tool install', PAR2 tools should be available but may need manual setup.\n\n"
    )

    if sys.platform.startswith("darwin"):  # macOS
        return base_msg + (
            "Install PAR2 on macOS:\n"
            "  brew install par2cmdline\n"
            "  or\n"
            "  brew install par2cmdline-turbo\n"
            "\nAlternatively, ensure the bundled PAR2 tool is accessible:\n"
            "  Check if 'which par2' returns a valid path"
        )
    elif sys.platform.startswith("linux"):  # Linux
        return base_msg + (
            "Install PAR2 on Linux:\n"
            "  Ubuntu/Debian: sudo apt install par2cmdline\n"
            "  CentOS/RHEL: sudo yum install par2cmdline\n"
            "  Arch: sudo pacman -S par2cmdline\n"
            "  or install par2cmdline-turbo for better performance\n"
            "\nAlternatively, ensure the bundled PAR2 tool is accessible:\n"
            "  Check if 'which par2' returns a valid path"
        )
    elif sys.platform.startswith("win"):  # Windows
        return base_msg + (
            "Install PAR2 on Windows:\n"
            "  Download from: https://github.com/Parchive/par2cmdline/releases\n"
            "  or use chocolatey: choco install par2cmdline\n"
            "  or use winget: winget install par2cmdline\n"
            "\nAlternatively, ensure the bundled PAR2 tool is accessible:\n"
            "  Check if 'par2.exe' is available in your PATH"
        )
    else:
        return base_msg + (
            "Install PAR2 for your platform:\n"
            "  Visit: https://github.com/Parchive/par2cmdline\n"
            "  or: https://github.com/animetosho/par2cmdline-turbo\n"
            "\nAlternatively, ensure the bundled PAR2 tool is accessible in your PATH"
        )
