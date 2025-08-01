# Changelog

All notable changes to coldpack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Enhanced compression algorithm selection
- Archive metadata database
- Incremental archive updates
- Advanced filtering options

## [0.2.0] - 2025-08-02

### Added
- **Enhanced Cross-Platform Support**: Complete migration to py7zz v1.0.0 with native Windows filename handling
- **Improved Performance**: Optimized archive information API for faster directory listing operations
- **Better Error Handling**: Enhanced debugging with descriptive error logging throughout the system

### Changed
- **Simplified Architecture**: Removed 3,000+ lines of legacy workaround code now handled natively by py7zz
- **Enhanced Directory Detection**: Multiple detection methods using py7zz API (is_dir(), isdir(), type checking)
- **Consistent File Ordering**: Improved file sorting and pagination for better user experience

### Fixed
- **Archive Listing**: Resolved directory detection issues across different archive formats
- **Cross-Platform Compatibility**: Native filename sanitization eliminates Windows-specific path problems
- **Security**: Added proper error logging to replace silent exception handling

### Removed
- **Legacy Code**: Eliminated complex Windows-specific filename workarounds
- **Obsolete Tests**: Removed Windows-specific filename handling tests no longer needed

## [0.2.0a2] - 2025-08-02

### Changed
- **Cross-Platform Compatibility**: Enhanced Windows filename handling through improved py7zz integration
- **Code Architecture**: Streamlined internal filename processing for better reliability

## [0.1.1] - 2025-07-26

### Fixed
- **Console Output**: Resolved unwanted debug messages during normal operation
- **Temporary File Cleanup**: Improved reliability on Windows systems
- **PAR2 Tool Detection**: Enhanced compatibility with uv tool installations

## [0.1.0] - 2025-07-26

### Added
- **7z Cold Storage**: Complete CLI tool for creating standardized 7z archives
- **Multi-Format Support**: Import from 7z, zip, tar, rar, and directory sources
- **4-Layer Verification**: Comprehensive integrity checking (7z + SHA-256 + BLAKE3 + PAR2)
- **Dynamic Compression**: Intelligent optimization based on file size (7 tiers)
- **PAR2 Recovery**: Automatic generation of 10% redundancy for error correction
- **Cross-Platform Support**: Full compatibility across Windows, macOS, and Linux
- **Complete CLI Suite**: create, extract, verify, repair, info, and list commands

## [0.1.0b5] - 2025-07-26

### Fixed
- **Cross-Platform Compatibility**: Resolved directory detection issues on Windows

## [0.1.0b4] - 2025-07-24

### Added
- **Advanced File Listing**: Complete list command with filtering and pagination
- **Pre-Extraction Verification**: Optional integrity checking before extraction

## [0.1.0b3] - 2025-07-22

### Added
- **Automatic Parameter Recovery**: Seamless restoration of compression settings during extraction
- **Enhanced Info Display**: Professional tree-structured archive information

## [0.1.0b2] - 2025-07-21

### Added
- **7z-Exclusive Architecture**: Simplified workflow focused on 7z cold storage
- **Dynamic Compression Optimization**: 7-tier intelligent parameter selection

## [0.1.0b1] - 2025-07-20

### Added
- **Core Functionality**: Initial implementation of multi-format archive processing
- **Verification System**: Basic integrity checking and PAR2 recovery infrastructure

[Unreleased]: https://github.com/RxChi1d/coldpack/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/RxChi1d/coldpack/releases/tag/v0.2.0
[0.2.0a2]: https://github.com/RxChi1d/coldpack/releases/tag/v0.2.0a2
[0.1.1]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.1
[0.1.0]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0
[0.1.0b5]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0b5
[0.1.0b4]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0b4
[0.1.0b3]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0b3
[0.1.0b2]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0b2
[0.1.0b1]: https://github.com/RxChi1d/coldpack/releases/tag/v0.1.0b1
