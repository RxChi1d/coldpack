"""Typer-based CLI interface for coldpack cold storage archiver."""

import sys
from pathlib import Path
from typing import Any, Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.constants import SUPPORTED_INPUT_FORMATS, ExitCodes
from .config.settings import CompressionSettings, ProcessingOptions
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier
from .utils.filesystem import format_file_size, get_file_size
from .utils.par2 import PAR2Manager, check_par2_availability, install_par2_instructions
from .utils.progress import ProgressTracker

# Initialize Typer app
app = typer.Typer(
    name="cpack",
    help="coldpack - Cross-platform cold storage CLI package for standardized tar.zst archives",
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Initialize Rich console
console = Console()


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print(f"coldpack version {__version__}")
        raise typer.Exit()


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()  # Remove default handler

    if quiet:
        level = "WARNING"
        format_str = "<level>{message}</level>"
    elif verbose:
        level = "DEBUG"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    else:
        level = "INFO"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

    logger.add(sys.stderr, level=level, format=format_str, colorize=True)


def get_global_options(ctx: typer.Context) -> tuple[bool, bool]:
    """Get global verbose and quiet options from context."""
    if ctx.obj is None:
        return False, False
    return ctx.obj.get("verbose", False), ctx.obj.get("quiet", False)


def _load_coldpack_metadata(
    archive: Path, verbose: bool = False
) -> tuple[Optional[Any], Optional[str]]:
    """Load metadata.toml for coldpack standard archives.

    For coldpack standard compliance, metadata.toml must be in the standard location:
    archive_directory/metadata/metadata.toml

    Args:
        archive: Path to the archive file
        verbose: Enable verbose logging

    Returns:
        Tuple of (ArchiveMetadata object if found, error message if corrupted)
        - (metadata, None): Successfully loaded metadata
        - (None, None): No metadata file found (not a coldpack archive)
        - (None, error_msg): Metadata file exists but is corrupted
    """
    from .config.settings import ArchiveMetadata

    # Standard coldpack structure: archive_dir/metadata/metadata.toml
    metadata_path = archive.parent / "metadata" / "metadata.toml"

    if metadata_path.exists():
        try:
            metadata = ArchiveMetadata.load_from_toml(metadata_path)
            if verbose:
                logger.info(f"Loading coldpack metadata from: {metadata_path}")
            return metadata, None
        except Exception as e:
            # If metadata.toml exists but is corrupted, return error but don't raise
            error_msg = f"Corrupted metadata.toml at {metadata_path}: {e}"
            logger.warning(error_msg)
            return None, error_msg

    if verbose:
        logger.debug(
            f"No coldpack metadata found for {archive} (not a coldpack archive)"
        )
    return None, None


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output (increase log level)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Quiet output (decrease log level)",
    ),
) -> None:
    """coldpack - Cross-platform cold storage CLI package."""
    # Validate that verbose and quiet are not used together
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    # Store global options in context
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@app.command()
def archive(
    ctx: typer.Context,
    source: Path,
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
        show_default="current directory",
        rich_help_panel="Output Options",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Archive name",
        show_default="source name",
        rich_help_panel="Output Options",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing files",
        rich_help_panel="Output Options",
    ),
    level: int = typer.Option(
        19,
        "--level",
        "-l",
        help="Compression level (1-22)",
        show_default=True,
        rich_help_panel="Compression Options",
    ),
    threads: int = typer.Option(
        0,
        "--threads",
        "-t",
        help="Number of threads",
        show_default="auto-detect",
        rich_help_panel="Compression Options",
    ),
    no_long: bool = typer.Option(
        False,
        "--no-long",
        help="Disable automatic long-distance matching",
        rich_help_panel="Compression Options",
    ),
    long_distance: Optional[int] = typer.Option(
        None,
        "--long-distance",
        help="Set long-distance matching value (disables auto-adjustment)",
        rich_help_panel="Compression Options",
    ),
    no_par2: bool = typer.Option(
        False,
        "--no-par2",
        help="Skip PAR2 recovery file generation",
        rich_help_panel="PAR2 Options",
    ),
    no_verify: bool = typer.Option(
        False,
        "--no-verify",
        help="Skip all integrity verification (overrides individual controls)",
        rich_help_panel="Verification Options",
    ),
    # Individual verification layer controls for archive creation
    no_verify_tar: bool = typer.Option(
        False,
        "--no-verify-tar",
        help="Skip TAR header verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_zstd: bool = typer.Option(
        False,
        "--no-verify-zstd",
        help="Skip Zstd integrity verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_sha256: bool = typer.Option(
        False,
        "--no-verify-sha256",
        help="Skip SHA-256 hash verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_blake3: bool = typer.Option(
        False,
        "--no-verify-blake3",
        help="Skip BLAKE3 hash verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_par2: bool = typer.Option(
        False,
        "--no-verify-par2",
        help="Skip PAR2 recovery verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    par2_redundancy: int = typer.Option(
        10,
        "--par2-redundancy",
        "-r",
        help="PAR2 redundancy percentage",
        show_default=True,
        rich_help_panel="PAR2 Options",
    ),
    # Global Options
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Create a cold storage archive with comprehensive verification.

    Args:
        ctx: Typer context
        source: Source file, directory, or archive to process
        output_dir: Output directory (default: current directory)
        name: Archive name (default: source name)
        force: Force overwrite existing files
        level: Compression level (1-22)
        threads: Number of threads (0=auto)
        no_long: Disable automatic long-distance matching
        long_distance: Set long-distance matching value (disables auto-adjustment)
        no_par2: Skip PAR2 recovery file generation
        no_verify: Skip all integrity verification (overrides individual controls)
        no_verify_tar: Skip TAR header verification during archive creation
        no_verify_zstd: Skip Zstd integrity verification during archive creation
        no_verify_sha256: Skip SHA-256 hash verification during archive creation
        no_verify_blake3: Skip BLAKE3 hash verification during archive creation
        no_verify_par2: Skip PAR2 recovery verification during archive creation
        par2_redundancy: PAR2 redundancy percentage
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate long-distance matching parameters
    if no_long and long_distance is not None:
        console.print(
            "[red]Error: --no-long and --long-distance cannot be used together[/red]"
        )
        raise typer.Exit(1)

    # Validate verification parameters
    if no_verify and any(
        [
            no_verify_tar,
            no_verify_zstd,
            no_verify_sha256,
            no_verify_blake3,
            no_verify_par2,
        ]
    ):
        console.print(
            "[red]Error: --no-verify cannot be used with individual --no-verify-* options[/red]"
        )
        console.print(
            "[yellow]Use either --no-verify to skip all verification, or specific --no-verify-* options[/yellow]"
        )
        raise typer.Exit(1)

    # Validate source
    if not source.exists():
        console.print(f"[red]Error: Source not found: {source}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output_dir is None:
        output_dir = Path.cwd()

    try:
        # Check PAR2 availability if needed
        if not no_par2 and not check_par2_availability():
            console.print(
                "[yellow]Warning: PAR2 tools not found, recovery files will not be generated[/yellow]"
            )
            console.print(install_par2_instructions())
            no_par2 = True

        # Configure compression settings
        # If long_distance is specified, it overrides long_mode
        if long_distance is not None:
            final_long_mode = True  # Enable for manual setting
            final_long_distance = long_distance
        else:
            final_long_mode = not no_long
            final_long_distance = None

        compression_settings = CompressionSettings(
            level=level,
            threads=threads,
            long_mode=final_long_mode,
            long_distance=final_long_distance,
            ultra_mode=(level >= 20),
        )

        # Configure processing options
        # Handle verification settings: no_verify overrides individual controls
        if no_verify:
            # Skip all verification
            final_verify_integrity = False
            final_verify_tar = False
            final_verify_zstd = False
            final_verify_sha256 = False
            final_verify_blake3 = False
            final_verify_par2 = False
        else:
            # Use individual controls
            final_verify_integrity = True
            final_verify_tar = not no_verify_tar
            final_verify_zstd = not no_verify_zstd
            final_verify_sha256 = not no_verify_sha256
            final_verify_blake3 = not no_verify_blake3
            final_verify_par2 = not no_verify_par2

        processing_options = ProcessingOptions(
            verify_integrity=final_verify_integrity,
            verify_tar=final_verify_tar,
            verify_zstd=final_verify_zstd,
            verify_sha256=final_verify_sha256,
            verify_blake3=final_verify_blake3,
            verify_par2=final_verify_par2,
            generate_par2=not no_par2,
            par2_redundancy=par2_redundancy,
            verbose=final_verbose,
            force_overwrite=force,
        )

        # Configure PAR2 settings
        from .config.settings import PAR2Settings

        par2_settings = PAR2Settings(redundancy_percent=par2_redundancy)

        # Create archiver
        archiver = ColdStorageArchiver(
            compression_settings, processing_options, par2_settings
        )

        # Create progress tracker
        with ProgressTracker(console):
            console.print(f"[cyan]Creating cold storage archive from: {source}[/cyan]")
            console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

            # Create archive
            result = archiver.create_archive(source, output_dir, name)

            if result.success:
                console.print("[green]✓ Archive created successfully![/green]")

                # Display summary
                display_archive_summary(result)

            else:
                console.print(f"[red]✗ Archive creation failed: {result.message}[/red]")
                if verbose and result.error_details:
                    console.print(f"[red]Details: {result.error_details}[/red]")
                raise typer.Exit(ExitCodes.COMPRESSION_FAILED)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from None
    except Exception as e:
        logger.error(f"Archive creation failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


@app.command()
def extract(
    ctx: typer.Context,
    archive: Path,
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
        show_default="current directory",
        rich_help_panel="Output Options",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing files",
        rich_help_panel="Output Options",
    ),
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Extract a cold storage archive or supported archive format.

    For coldpack archives (.tar.zst with metadata/metadata.toml):
    - Automatically uses original compression parameters from metadata
    - Falls back to direct extraction if metadata is unavailable
    - Errors if metadata is corrupted or extraction fails without metadata

    Args:
        ctx: Typer context
        archive: Archive file to extract
        output_dir: Output directory (default: current directory)
        force: Force overwrite existing files
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output_dir is None:
        output_dir = Path.cwd()

    try:
        console.print(f"[cyan]Extracting archive: {archive}[/cyan]")
        console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

        # Step 1: Try to load coldpack metadata (standard compliant archives)
        metadata, metadata_error = _load_coldpack_metadata(archive, final_verbose)

        extractor = MultiFormatExtractor()

        if metadata:
            # Step 2a: Standard coldpack archive - use original parameters
            console.print(
                "[cyan]Coldpack archive detected - using original compression parameters[/cyan]"
            )
            console.print(
                f"[cyan]  Compression level: {metadata.compression_settings.level}[/cyan]"
            )
            console.print(
                f"[cyan]  Threads: {metadata.compression_settings.threads}[/cyan]"
            )
            console.print(
                f"[cyan]  Long distance: {metadata.compression_settings.long_mode}[/cyan]"
            )

            # Extract with metadata
            extracted_path = extractor.extract(
                archive, output_dir, force_overwrite=force, metadata=metadata
            )
        else:
            # Step 2b: Non-coldpack archive, missing metadata, or corrupted metadata - attempt direct extraction
            if metadata_error:
                # Warn about corrupted metadata but continue with direct extraction
                console.print(f"[yellow]Warning: {metadata_error}[/yellow]")
                console.print(
                    "[yellow]Attempting direct extraction without metadata...[/yellow]"
                )
            elif final_verbose:
                console.print(
                    "[yellow]No coldpack metadata found - attempting direct extraction[/yellow]"
                )

            try:
                extracted_path = extractor.extract(
                    archive, output_dir, force_overwrite=force, metadata=None
                )
            except Exception as direct_extract_error:
                # Step 3: Direct extraction failed
                logger.error(f"Direct extraction failed: {direct_extract_error}")

                if metadata_error:
                    # Both metadata is corrupted AND direct extraction failed
                    console.print(
                        "[red]Error: Archive extraction failed. The metadata is corrupted and direct extraction also failed.[/red]"
                    )
                    console.print(f"[red]Metadata error: {metadata_error}[/red]")
                    console.print(
                        f"[red]Extraction error: {direct_extract_error}[/red]"
                    )
                else:
                    # No metadata but direct extraction failed
                    console.print(
                        "[red]Error: Archive extraction failed. This may not be a valid coldpack archive or the format is unsupported.[/red]"
                    )
                    console.print(f"[red]Details: {direct_extract_error}[/red]")

                raise typer.Exit(ExitCodes.EXTRACTION_FAILED) from direct_extract_error

        console.print("[green]✓ Extraction completed successfully![/green]")
        console.print(f"[green]Extracted to: {extracted_path}[/green]")

    except typer.Exit:
        # Re-raise typer.Exit to preserve exit codes
        raise
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.EXTRACTION_FAILED) from e


@app.command()
def verify(
    ctx: typer.Context,
    archive: Path,
    hash_files: Optional[list[Path]] = typer.Option(
        None,
        "--hash-files",
        help="Hash files for verification",
        rich_help_panel="Input Options",
    ),
    par2_file: Optional[Path] = typer.Option(
        None,
        "--par2-file",
        "-p",
        help="PAR2 recovery file",
        rich_help_panel="Input Options",
    ),
    # Individual verification layer controls
    no_tar: bool = typer.Option(
        False,
        "--no-tar",
        help="Skip TAR header verification",
        rich_help_panel="Verification Controls",
    ),
    no_zstd: bool = typer.Option(
        False,
        "--no-zstd",
        help="Skip Zstd integrity verification",
        rich_help_panel="Verification Controls",
    ),
    no_sha256: bool = typer.Option(
        False,
        "--no-sha256",
        help="Skip SHA-256 hash verification",
        rich_help_panel="Verification Controls",
    ),
    no_blake3: bool = typer.Option(
        False,
        "--no-blake3",
        help="Skip BLAKE3 hash verification",
        rich_help_panel="Verification Controls",
    ),
    no_par2: bool = typer.Option(
        False,
        "--no-par2",
        help="Skip PAR2 recovery verification",
        rich_help_panel="Verification Controls",
    ),
    # Local verbose/quiet override
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Verify archive integrity using multiple verification layers.

    Args:
        ctx: Typer context
        archive: Archive file to verify
        hash_files: Hash files for verification
        par2_file: PAR2 recovery file
        no_tar: Skip TAR header verification
        no_zstd: Skip Zstd integrity verification
        no_sha256: Skip SHA-256 hash verification
        no_blake3: Skip BLAKE3 hash verification
        no_par2: Skip PAR2 recovery verification
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        verifier = ArchiveVerifier()

        console.print(f"[cyan]Verifying archive: {archive}[/cyan]")

        # Configure which verification layers to skip
        skip_layers = set()
        if no_tar:
            skip_layers.add("tar_header")
        if no_zstd:
            skip_layers.add("zstd_integrity")
        if no_sha256:
            skip_layers.add("sha256_hash")
        if no_blake3:
            skip_layers.add("blake3_hash")
        if no_par2:
            skip_layers.add("par2_recovery")

        # Handle explicitly provided files
        if hash_files or par2_file:
            # Build hash file dictionary from explicit files
            hash_file_dict = {}
            if hash_files:
                for hash_file in hash_files:
                    if (
                        hash_file.suffix == ".sha256"
                        and "sha256_hash" not in skip_layers
                    ):
                        hash_file_dict["sha256"] = hash_file
                    elif (
                        hash_file.suffix == ".blake3"
                        and "blake3_hash" not in skip_layers
                    ):
                        hash_file_dict["blake3"] = hash_file

            # Use manual verification with explicitly provided files
            results = verifier.verify_complete(archive, hash_file_dict, par2_file)
        else:
            # Use auto-discovery verification (recommended approach)
            results = verifier.verify_auto(archive, skip_layers)

        # Display results
        display_verification_results(results)

        # Check overall success
        failed_results = [r for r in results if not r.success]
        if failed_results:
            raise typer.Exit(ExitCodes.VERIFICATION_FAILED)

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.VERIFICATION_FAILED) from e


@app.command()
def repair(
    ctx: typer.Context,
    par2_file: Path,
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Repair a corrupted archive using PAR2 recovery files.

    Args:
        ctx: Typer context
        par2_file: PAR2 recovery file
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate PAR2 file
    if not par2_file.exists():
        console.print(f"[red]Error: PAR2 file not found: {par2_file}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        # Try to load metadata for PAR2 parameter recovery
        metadata = None
        redundancy_percent = 10  # default

        try:
            from .config.settings import ArchiveMetadata

            # Look for metadata.toml in the same directory as PAR2 file
            metadata_paths = [
                par2_file.parent / "metadata.toml",
                par2_file.parent.parent / "metadata" / "metadata.toml",
            ]

            for metadata_path in metadata_paths:
                if metadata_path.exists():
                    try:
                        metadata = ArchiveMetadata.load_from_toml(metadata_path)
                        redundancy_percent = metadata.par2_settings.redundancy_percent
                        logger.debug(
                            f"Using PAR2 parameters from metadata: {redundancy_percent}% redundancy"
                        )
                        break
                    except Exception as e:
                        logger.debug(
                            f"Could not load metadata from {metadata_path}: {e}"
                        )
        except Exception as e:
            logger.debug(f"Metadata loading failed: {e}")

        repairer = ArchiveRepairer(redundancy_percent=redundancy_percent)

        console.print(f"[cyan]Attempting repair using: {par2_file}[/cyan]")
        if metadata:
            console.print(
                f"[cyan]Using original PAR2 settings: {redundancy_percent}% redundancy[/cyan]"
            )

        # Check repair capability
        capability = repairer.check_repair_capability(par2_file)

        if not capability["can_repair"]:
            console.print(
                "[red]✗ Archive cannot be repaired with available recovery data[/red]"
            )
            raise typer.Exit(ExitCodes.GENERAL_ERROR)

        # Perform repair
        result = repairer.repair_archive(par2_file)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
            if result.repaired_files:
                console.print(
                    f"[green]Repaired files: {', '.join(result.repaired_files)}[/green]"
                )
        else:
            console.print(f"[red]✗ {result.message}[/red]")
            if verbose and result.error_details:
                console.print(f"[red]Details: {result.error_details}[/red]")
            raise typer.Exit(ExitCodes.GENERAL_ERROR)

    except Exception as e:
        logger.error(f"Repair failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


@app.command()
def info(
    ctx: typer.Context,
    path: Path,
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Display information about an archive or PAR2 recovery files.

    Args:
        ctx: Typer context
        path: Archive file or PAR2 file to analyze
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate path
    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        if path.suffix == ".par2":
            # PAR2 file info
            display_par2_info(path)
        else:
            # Archive file info
            display_archive_info(path)

    except Exception as e:
        logger.error(f"Info retrieval failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


def display_archive_summary(result: Any) -> None:
    """Display archive creation summary."""
    if not result.metadata:
        return

    table = Table(
        title="Archive Summary", show_header=True, header_style="bold magenta"
    )
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    metadata = result.metadata

    table.add_row("Archive", str(metadata.archive_path.name))
    table.add_row("Original Size", format_file_size(metadata.original_size))
    table.add_row("Compressed Size", format_file_size(metadata.compressed_size))
    table.add_row("Compression Ratio", f"{metadata.compression_percentage:.1f}%")
    table.add_row("Files", str(metadata.file_count))
    table.add_row("Compression Level", str(metadata.compression_settings.level))

    if metadata.verification_hashes:
        for algorithm, hash_value in metadata.verification_hashes.items():
            table.add_row(f"{algorithm.upper()} Hash", hash_value[:16] + "...")

    if metadata.par2_files:
        table.add_row("PAR2 Files", str(len(metadata.par2_files)))

    console.print(table)


def display_verification_results(results: Any) -> None:
    """Display verification results table."""
    table = Table(
        title="Verification Results", show_header=True, header_style="bold magenta"
    )
    table.add_column("Layer", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for result in results:
        status = "[green]✓ PASS[/green]" if result.success else "[red]✗ FAIL[/red]"
        table.add_row(result.layer.replace("_", " ").title(), status, result.message)

    console.print(table)

    # Summary
    passed = sum(1 for r in results if r.success)
    total = len(results)

    if passed == total:
        console.print(f"[green]All {total} verification layers passed![/green]")
    else:
        console.print(
            f"[red]{total - passed} of {total} verification layers failed![/red]"
        )


def display_archive_info(archive_path: Path) -> None:
    """Display archive information, prioritizing metadata.toml if available."""
    from .config.settings import ArchiveMetadata

    try:
        # First, try to find and load metadata.toml
        metadata = None

        # Determine archive name for path construction
        archive_name = archive_path.stem
        if archive_name.endswith(".tar"):
            archive_name = archive_name[:-4]

        metadata_paths = [
            # Standard coldpack structure: archive_dir/metadata/metadata.toml
            archive_path.parent / "metadata" / "metadata.toml",
            # Alternative: archive_name_dir/metadata/metadata.toml
            archive_path.parent / archive_name / "metadata" / "metadata.toml",
            # Legacy location: same directory as archive
            archive_path.parent / "metadata.toml",
        ]

        for metadata_path in metadata_paths:
            if metadata_path.exists():
                try:
                    metadata = ArchiveMetadata.load_from_toml(metadata_path)
                    break
                except Exception as e:
                    logger.debug(f"Could not load metadata from {metadata_path}: {e}")

        if metadata:
            # Display comprehensive metadata information
            display_metadata_info(archive_path, metadata)
        else:
            # Fallback to basic archive analysis
            display_basic_archive_info(archive_path)

    except Exception as e:
        console.print(f"[red]Could not read archive info: {e}[/red]")


def display_metadata_info(archive_path: Path, metadata: Any) -> None:
    """Display comprehensive archive information from metadata."""
    # Archive Basic Information
    basic_table = Table(
        title=f"Archive: {archive_path.name}",
        show_header=False,
        header_style="bold cyan",
        title_style="bold white",
        border_style="dim",
    )
    basic_table.add_column("Property", style="dim", no_wrap=True, width=20)
    basic_table.add_column("Value", style="white")

    basic_table.add_row("Path", str(archive_path))
    basic_table.add_row("Format", "TAR + Zstandard")

    # Calculate size display with compression info
    original_size_str = format_file_size(metadata.original_size)
    compressed_size_str = format_file_size(metadata.compressed_size)
    compression_pct = metadata.compression_percentage

    size_info = f"{compressed_size_str} ({original_size_str} → {compressed_size_str}, {compression_pct:.1f}% compression)"
    basic_table.add_row("Size", size_info)

    console.print(basic_table)

    # Content Summary
    content_table = Table(
        title="Content Summary",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    content_table.add_column("Item", style="dim", no_wrap=True, width=20)
    content_table.add_column("Value", style="green")

    content_table.add_row("├── Files", str(metadata.file_count))
    content_table.add_row("├── Directories", str(metadata.directory_count))
    content_table.add_row("├── Total Size", original_size_str)
    content_table.add_row("└── Compression", f"{compression_pct:.1f}%")

    console.print(content_table)

    # Creation Settings
    creation_table = Table(
        title="Creation Settings",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    creation_table.add_column("Setting", style="dim", no_wrap=True, width=20)
    creation_table.add_column("Value", style="yellow")

    creation_table.add_row("├── Zstd Level", str(metadata.compression_settings.level))

    # Handle long distance display
    if metadata.compression_settings.long_distance is not None:
        long_display = str(metadata.compression_settings.long_distance)
    else:
        long_display = "true" if metadata.compression_settings.long_mode else "false"
    creation_table.add_row("├── Long Distance", long_display)

    creation_table.add_row("├── Threads", str(metadata.compression_settings.threads))
    creation_table.add_row("└── TAR Method", metadata.tar_settings.method.title())

    console.print(creation_table)

    # Integrity information
    if metadata.verification_hashes:
        integrity_table = Table(
            title="Integrity",
            show_header=False,
            title_style="bold cyan",
            border_style="dim",
        )
        integrity_table.add_column("Algorithm", style="dim", no_wrap=True, width=20)
        integrity_table.add_column("Hash", style="bright_blue")

        # Display hashes with checkmark if available
        hash_algorithms = ["sha256", "blake3"]
        for i, algorithm in enumerate(hash_algorithms):
            if algorithm in metadata.verification_hashes:
                hash_value = metadata.verification_hashes[algorithm]
                # Truncate hash for display
                display_hash = f"{hash_value[:16]}... ✓"
                prefix = "├──" if i < len(hash_algorithms) - 1 else "├──"
                integrity_table.add_row(f"{prefix} {algorithm.upper()}", display_hash)

        # Add PAR2 info if available
        if metadata.par2_settings:
            par2_info = f"{metadata.par2_settings.redundancy_percent}% redundancy"
            if metadata.par2_files:
                par2_info += f", {len(metadata.par2_files)} recovery file{'s' if len(metadata.par2_files) > 1 else ''} ✓"
            else:
                par2_info += " (no files generated)"
            integrity_table.add_row("└── PAR2", par2_info)

        console.print(integrity_table)

    # Metadata information
    metadata_table = Table(
        title="Metadata",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    metadata_table.add_column("Property", style="dim", no_wrap=True, width=20)
    metadata_table.add_column("Value", style="magenta")

    metadata_table.add_row(
        "├── Created", metadata.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    metadata_table.add_row("├── coldpack", f"v{metadata.coldpack_version}")

    # Check for related files and show their status
    related_files = []
    archive_dir = archive_path.parent
    archive_name = archive_path.stem
    if archive_name.endswith(".tar"):
        archive_name = archive_name[:-4]  # Remove .tar from .tar.zst

    # Check for hash files
    sha256_file = archive_dir / f"{archive_path.name}.sha256"
    blake3_file = archive_dir / f"{archive_path.name}.blake3"

    # Check for PAR2 files (can be in same directory or metadata subdirectory)
    par2_file = archive_dir / f"{archive_path.name}.par2"
    metadata_par2_file = archive_dir / "metadata" / f"{archive_path.name}.par2"

    if sha256_file.exists():
        related_files.append(f"{archive_path.name}.sha256")
    if blake3_file.exists():
        related_files.append(f"{archive_path.name}.blake3")
    if par2_file.exists():
        related_files.append(f"{archive_path.name}.par2")
    elif metadata_par2_file.exists():
        related_files.append(f"metadata/{archive_path.name}.par2")

    if related_files:
        related_files_str = ", ".join(related_files)
        metadata_table.add_row("└── Related Files", related_files_str)
    else:
        metadata_table.add_row("└── Related Files", "[dim]None found[/dim]")

    console.print(metadata_table)


def display_basic_archive_info(archive_path: Path) -> None:
    """Display basic archive information when metadata is not available."""
    try:
        extractor = MultiFormatExtractor()
        info = extractor.get_archive_info(archive_path)

        # Archive basic information
        basic_table = Table(
            title=f"Archive: {archive_path.name}",
            show_header=False,
            title_style="bold white",
            border_style="dim",
        )
        basic_table.add_column("Property", style="dim", no_wrap=True, width=20)
        basic_table.add_column("Value", style="white")

        basic_table.add_row("Path", str(archive_path))

        # Determine format based on file extension
        if archive_path.suffix.lower() == ".zst" and archive_path.stem.endswith(".tar"):
            format_display = "TAR + Zstandard"
        else:
            format_display = info["format"].upper()

        basic_table.add_row("Format", format_display)
        basic_table.add_row("Size", format_file_size(info["size"]))

        console.print(basic_table)

        # Content summary (limited info available)
        content_table = Table(
            title="Content Summary",
            show_header=False,
            title_style="bold cyan",
            border_style="dim",
        )
        content_table.add_column("Item", style="dim", no_wrap=True, width=20)
        content_table.add_column("Value", style="green")

        content_table.add_row("├── Files", str(info["file_count"]))
        content_table.add_row(
            "├── Single Root", "Yes" if info["has_single_root"] else "No"
        )
        if info.get("root_name"):
            content_table.add_row("└── Root Directory", info["root_name"])
        else:
            content_table.add_row("└── Root Directory", "[dim]Multiple roots[/dim]")

        console.print(content_table)

        # Warning about limited information
        console.print(
            "\n[yellow]⚠️  Limited information available - no metadata file found.[/yellow]"
        )
        console.print(
            "[dim]For complete archive information, ensure the metadata/ directory is present.[/dim]"
        )
        console.print("[dim]Use 'cpack list' to view archive contents.[/dim]")

    except Exception as e:
        console.print(f"[red]Could not read basic archive info: {e}[/red]")


def display_par2_info(par2_path: Path) -> None:
    """Display PAR2 recovery file information."""
    try:
        par2_manager = PAR2Manager()
        info = par2_manager.get_recovery_info(par2_path)

        # PAR2 Recovery Information
        par2_table = Table(
            title=f"PAR2 Recovery: {par2_path.name}",
            show_header=False,
            title_style="bold white",
            border_style="dim",
        )
        par2_table.add_column("Property", style="dim", no_wrap=True, width=20)
        par2_table.add_column("Value", style="green")

        par2_table.add_row("Path", str(par2_path))
        par2_table.add_row("Redundancy", f"{info['redundancy_percent']}%")
        par2_table.add_row("Recovery Files", str(info["file_count"]))
        par2_table.add_row("Total Size", format_file_size(info["total_size"]))

        console.print(par2_table)

        # Recovery files list with tree-like display
        if info["par2_files"]:
            files_table = Table(
                title="Recovery Files",
                show_header=False,
                title_style="bold cyan",
                border_style="dim",
            )
            files_table.add_column("File", style="dim", no_wrap=True, width=30)
            files_table.add_column("Size", style="yellow", justify="right")

            for i, par2_file in enumerate(info["par2_files"]):
                file_path = Path(par2_file)
                if file_path.exists():
                    size = format_file_size(get_file_size(file_path))
                    prefix = "├──" if i < len(info["par2_files"]) - 1 else "└──"
                    files_table.add_row(f"{prefix} {file_path.name}", size)
                else:
                    prefix = "├──" if i < len(info["par2_files"]) - 1 else "└──"
                    files_table.add_row(
                        f"{prefix} {file_path.name}", "[red]Missing[/red]"
                    )

            console.print(files_table)

    except Exception as e:
        console.print(f"[red]Could not read PAR2 info: {e}[/red]")


@app.command()
def formats() -> None:
    """List supported archive formats."""
    console.print("[bold]Supported Input Formats:[/bold]")

    for fmt in sorted(SUPPORTED_INPUT_FORMATS):
        console.print(f"  {fmt}")

    console.print(
        f"\n[bold]Total:[/bold] {len(SUPPORTED_INPUT_FORMATS)} formats supported"
    )
    console.print(
        "[bold]Output Format:[/bold] .tar.zst (TAR archive compressed with Zstandard)"
    )


def cli_main() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(ExitCodes.GENERAL_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(ExitCodes.GENERAL_ERROR)


if __name__ == "__main__":
    cli_main()
