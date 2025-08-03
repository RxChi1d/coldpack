# Installation Guide

Installation instructions for coldpack.

## System Requirements

### Supported Platforms
- **Windows**: Windows 10/11, Windows Server 2019/2022
- **macOS**: macOS 10.15+ (Catalina and later)
- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 10+, Fedora 30+

### Python Requirements
- **Python Version**: 3.9, 3.10, 3.11, 3.12, or 3.13
- **Architecture**: x86_64 (64-bit) recommended
- **Virtual Environment**: Highly recommended for isolation

### System Dependencies
All required tools are automatically installed via PyPI packages:
- **py7zz**: Multi-format archive extraction (includes 7zz binary)
- **par2cmdline-turbo**: High-performance PAR2 operations

## Installation Methods

### Method 1: PyPI Installation (Recommended)

#### Using pip
```bash
# Install latest stable version
pip install coldpack

# Install specific version
pip install coldpack==0.1.0

# Upgrade existing installation
pip install --upgrade coldpack
```

#### Using uv (Modern Python Package Manager)
```bash
# Install coldpack
uv add coldpack

# Install in existing project
uv add coldpack --dev  # For development dependencies
```

### Method 2: Development Installation

#### Prerequisites
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix/Linux/macOS
# or
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```

#### Clone and Install
```bash
# Clone repository
git clone https://github.com/rxchi1d/coldpack.git
cd coldpack

# Create virtual environment and install dependencies
uv sync --dev

# Activate virtual environment
source .venv/bin/activate  # Unix/Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

#### Development Dependencies
The development installation includes:
- **Testing**: pytest, pytest-cov
- **Code Quality**: ruff, mypy
- **Documentation**: Additional tools for docs generation
- **Build Tools**: hatchling, hatch-vcs

## Virtual Environment Management

### Using venv (Built-in)
```bash
# Create virtual environment
python -m venv coldpack-env

# Activate environment
source coldpack-env/bin/activate  # Unix/Linux/macOS
coldpack-env\Scripts\activate     # Windows

# Install coldpack
pip install coldpack

# Deactivate when done
deactivate
```

### Using conda
```bash
# Create conda environment
conda create -n coldpack python=3.11
conda activate coldpack

# Install coldpack
pip install coldpack
```

### Using uv (Recommended)
```bash
# Create uv project
uv init coldpack-project
cd coldpack-project

# Add coldpack dependency
uv add coldpack

# Run commands in environment
uv run cpack --help
```

## Verification

### Installation Verification
```bash
# Check installation
cpack --version
# Expected output: coldpack version 0.1.0

# Verify all commands available
cpack --help
# Expected: List of all available commands

# Test archive creation
mkdir test-data
echo "Hello coldpack!" > test-data/sample.txt
cpack create test-data --output-dir ~/test-output
```

### Dependency Verification
```bash
# Python version check
python --version
# Expected: Python 3.9.x - 3.13.x

# Check core dependencies
python -c "import py7zz; print('py7zz OK')"
python -c "import blake3; print('BLAKE3 OK')"
```

## Platform-Specific Instructions

### Windows Installation

#### Windows Package Managers
```powershell
# Using Chocolatey
choco install python
pip install coldpack

# Using Scoop
scoop install python
pip install coldpack

# Using winget
winget install Python.Python.3.11
pip install coldpack
```

#### Windows-Specific Considerations
- **Path Length**: Ensure Windows supports long paths for deep directory structures
- **Permissions**: Install with appropriate user permissions
- **Antivirus**: Some antivirus software may interfere with PAR2 operations

### macOS Installation

#### Using Homebrew
```bash
# Install Python via Homebrew
brew install python@3.11

# Install coldpack
pip3.11 install coldpack

# Alternative: Use pipx for isolated installation
brew install pipx
pipx install coldpack
```

#### macOS-Specific Considerations
- **Code Signing**: py7zz binaries are properly signed for macOS Gatekeeper
- **System Integrity Protection**: No issues with SIP enabled
- **Apple Silicon**: Native support for M1/M2/M3 processors

### Linux Installation

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3.11 python3.11-pip python3.11-venv

# Install coldpack
pip3.11 install --user coldpack

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### CentOS/RHEL/Fedora
```bash
# Install Python (CentOS/RHEL)
sudo yum install python3.11 python3.11-pip

# Install Python (Fedora)
sudo dnf install python3.11 python3.11-pip

# Install coldpack
pip3.11 install --user coldpack
```

#### Arch Linux
```bash
# Install Python
sudo pacman -S python python-pip

# Install coldpack
pip install --user coldpack
```

## Docker Installation

### Official Docker Image
```dockerfile
FROM python:3.11-slim

# Install coldpack
RUN pip install coldpack

# Set working directory
WORKDIR /workspace

# Default command
CMD ["cpack", "--help"]
```

### Usage in Docker
```bash
# Build image
docker build -t coldpack-env .

# Run coldpack in container
docker run -v $(pwd):/workspace coldpack-env cpack create /workspace/data
```

## Troubleshooting

### Common Installation Issues

#### Permission Errors
```bash
# Solution 1: User installation
pip install --user coldpack

# Solution 2: Virtual environment
python -m venv venv
source venv/bin/activate
pip install coldpack
```

#### Python Version Issues
```bash
# Check Python version (must be 3.9+)
python --version

# If using multiple Python versions
python3.11 -m pip install coldpack
```

#### Network/Proxy Issues
```bash
# Configure pip for proxy
pip install --proxy http://proxy.company.com:8080 coldpack

# Use alternative index
pip install -i https://pypi.org/simple/ coldpack
```

### Platform-Specific Issues

#### Windows: Long Path Support
Enable long path support in Windows:
1. Open Local Group Policy Editor (`gpedit.msc`)
2. Navigate to: Computer Configuration > Administrative Templates > System > Filesystem
3. Enable "Enable Win32 long paths"

#### macOS: Command Not Found
```bash
# Add Python bin to PATH
echo 'export PATH="/usr/local/opt/python@3.11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

#### Linux: Missing System Libraries
```bash
# Ubuntu/Debian
sudo apt install build-essential python3-dev

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install python3-devel
```

## Uninstallation

### Complete Removal
```bash
# Uninstall coldpack
pip uninstall coldpack

# Remove configuration (optional)
rm -rf ~/.config/coldpack  # Linux/macOS
rmdir /s %APPDATA%\coldpack  # Windows

# Remove virtual environment (if used)
rm -rf coldpack-env
```

## Next Steps

After successful installation:

1. **Read the CLI Reference**: [CLI_REFERENCE.md](CLI_REFERENCE.md)
2. **Explore Examples**: [EXAMPLES.md](EXAMPLES.md)
3. **Learn Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Join Community**: [GitHub Discussions](https://github.com/rxchi1d/coldpack/discussions)

## Support

- **Installation Issues**: [GitHub Issues](https://github.com/rxchi1d/coldpack/issues)
- **General Questions**: [GitHub Discussions](https://github.com/rxchi1d/coldpack/discussions)
- **Documentation**: [Complete Documentation](../README.md)

---

**Installation Complete!** Ready to create 7z cold storage archives with `cpack`.
