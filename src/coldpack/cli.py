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
        )

        # Create archiver
        archiver = ColdStorageArchiver(compression_settings, processing_options)

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
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Extract a cold storage archive or supported archive format.

    Args:
        ctx: Typer context
        archive: Archive file to extract
        output_dir: Output directory (default: current directory)
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
        extractor = MultiFormatExtractor()

        console.print(f"[cyan]Extracting archive: {archive}[/cyan]")
        console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

        # Extract archive
        extracted_path = extractor.extract(archive, output_dir)

        console.print("[green]✓ Extraction completed successfully![/green]")
        console.print(f"[green]Extracted to: {extracted_path}[/green]")

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

        # Build hash file dictionary
        hash_file_dict = {}
        if hash_files:
            for hash_file in hash_files:
                if hash_file.suffix == ".sha256":
                    hash_file_dict["sha256"] = hash_file
                elif hash_file.suffix == ".blake3":
                    hash_file_dict["blake3"] = hash_file

        # Auto-detect hash files if not provided
        if not hash_file_dict:
            sha256_file = archive.with_suffix(archive.suffix + ".sha256")
            blake3_file = archive.with_suffix(archive.suffix + ".blake3")

            if sha256_file.exists() and not no_sha256:
                hash_file_dict["sha256"] = sha256_file
            if blake3_file.exists() and not no_blake3:
                hash_file_dict["blake3"] = blake3_file

        # Auto-detect PAR2 file if not provided
        if not par2_file and not no_par2:
            par2_candidate = archive.with_suffix(archive.suffix + ".par2")
            if par2_candidate.exists():
                par2_file = par2_candidate

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

        # Perform verification with layer controls
        # Note: We'll need to modify the verifier to accept skip_layers parameter
        results = verifier.verify_complete(archive, hash_file_dict, par2_file)

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
        repairer = ArchiveRepairer()

        console.print(f"[cyan]Attempting repair using: {par2_file}[/cyan]")

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
    """Display archive information."""
    try:
        extractor = MultiFormatExtractor()
        info = extractor.get_archive_info(archive_path)

        table = Table(
            title=f"Archive Information: {archive_path.name}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("File Path", str(archive_path))
        table.add_row("Format", info["format"])
        table.add_row("File Size", format_file_size(info["size"]))
        table.add_row("Files Count", str(info["file_count"]))
        table.add_row("Has Single Root", "Yes" if info["has_single_root"] else "No")

        if info.get("root_name"):
            table.add_row("Root Directory", info["root_name"])

        console.print(table)

        # Show some file names
        if info["files"]:
            console.print("\n[bold]Sample Files:[/bold]")
            for file_name in info["files"][:10]:
                console.print(f"  {file_name}")

            if len(info["files"]) > 10:
                console.print(f"  ... and {len(info['files']) - 10} more files")

    except Exception as e:
        console.print(f"[red]Could not read archive info: {e}[/red]")


def display_par2_info(par2_path: Path) -> None:
    """Display PAR2 recovery file information."""
    try:
        par2_manager = PAR2Manager()
        info = par2_manager.get_recovery_info(par2_path)

        table = Table(
            title=f"PAR2 Recovery Information: {par2_path.name}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Main PAR2 File", info["main_par2_file"])
        table.add_row("Recovery Files", str(info["file_count"]))
        table.add_row("Total Size", format_file_size(info["total_size"]))
        table.add_row("Redundancy", f"{info['redundancy_percent']}%")

        console.print(table)

        # Show recovery files
        if info["par2_files"]:
            console.print("\n[bold]Recovery Files:[/bold]")
            for par2_file in info["par2_files"]:
                file_path = Path(par2_file)
                if file_path.exists():
                    size = format_file_size(get_file_size(file_path))
                    console.print(f"  {file_path.name} ({size})")

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
