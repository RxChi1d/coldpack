name: "Coldpack Initial Implementation PRP - Cross-Platform Cold Storage CLI Package"
description: |

## Goal
建立一個跨平台的冷儲存 Python CLI 套件 "coldpack"，專門用於將指定的來源檔案或資料夾封存成標準化的冷儲存格式。套件將提供 `cpack` 命令，支援多種壓縮格式輸入並統一輸出為 tar.zst 格式，包含完整的驗證和修復機制。

## Why
- **標準化需求**: 提供統一的冷儲存解決方案，避免不同格式的管理複雜性
- **資料安全性**: 透過雙重雜湊驗證 (SHA-256 + BLAKE3) 和 PAR2 修復機制確保長期資料完整性
- **效能最佳化**: 使用現代壓縮演算法 (zstd) 和動態參數調整提供最佳壓縮比
- **使用者體驗**: 提供簡潔的 CLI 介面和美觀的進度顯示，降低學習成本

## What
建立完整的 coldpack Python 套件，包含：

### 核心功能
1. **多格式輸入支援**: 支援資料夾、7z、zip、tar.gz、rar 等格式
2. **統一輸出格式**: 產生 tar.zst 格式的冷儲存封存檔案
3. **完整驗證機制**: 5層驗證確保每步驟完整性
4. **修復冗餘**: PAR2 修復機制 (預設 10% 冗餘率)
5. **CLI 命令**: cpack archive/extract/verify/repair/info

### 技術特色
- 磁碟空間預檢機制
- 安全的臨時檔案管理
- 漂亮的進度顯示和統計報告
- 跨平台兼容性 (Windows、macOS、Linux)
- 動態系統規格檢測和參數最佳化

### Success Criteria
- [ ] 完整的 coldpack 套件，支援所有核心命令
- [ ] 所有測試通過，覆蓋率 ≥ 90%
- [ ] 跨平台相容性驗證 (Windows/macOS/Linux)
- [ ] 效能基準測試達到預期 (壓縮比 60-80%)
- [ ] 完整的文件和使用範例

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- file: examples/CLAUDE.md
  why: 開發規範、工具配置、語言規則、提交規範

- file: examples/pyproject.toml
  why: 專案配置參考、依賴管理、開發工具設定

- file: examples/VERSION_STRATEGY.md
  why: PEP 440 版本控制策略和發布流程

- file: examples/archive-compress.sh
  why: 詳細的處理流程實現，了解每個步驟的具體邏輯

- file: examples/API.md
  why: py7zz 套件 API 設計參考，包含多種 API 層級和使用模式

- url: https://github.com/rxchi1d/py7zz
  why: py7zz 官方 GitHub 儲存庫，包含完整 API 文件
  critical: 支援 async 操作、progress callbacks 和多種壓縮格式

- url: https://python-zstandard.readthedocs.io/en/latest/
  why: zstandard 壓縮 API 使用方法和最佳實踐
  critical: 使用 ZstdCompressor 和 ZstdDecompressor 類進行高效操作

- url: https://github.com/oconnor663/blake3-py
  why: BLAKE3 雜湊演算法 Python 綁定使用方法
  critical: 支援 keyed hashing 和 extendable output

- url: https://typer.tiangolo.com/
  why: Typer CLI 框架文件，用於建立現代 CLI 應用
  critical: 基於 type hints 的自動參數驗證和幫助生成

- url: https://rich.readthedocs.io/en/stable/progress.html
  why: Rich 進度條和終端美化輸出
  critical: Progress 類支援多任務並行進度顯示
```

### Current Codebase tree
```bash
coldpack/
├── CLAUDE.md                  # 已存在的開發規範
├── README.md                  # 專案說明
├── INITIAL.md                 # 功能規格
├── coldpack-implementation.md # 實施計畫
├── examples/                  # 參考範例
│   ├── CLAUDE.md             # 開發規範範本
│   ├── pyproject.toml        # 配置範本
│   ├── VERSION_STRATEGY.md   # 版本策略
│   ├── API.md                # API 設計參考
│   └── archive-compress.sh   # 實現邏輯參考
└── PRPs/                     # PRP 文件
    └── templates/
        └── prp_base.md
```

### Desired Codebase tree with files to be added and responsibility of file
```bash
coldpack/
├── src/
│   └── coldpack/
│       ├── __init__.py         # 匯出主要 API，版本資訊
│       ├── cli.py              # Typer CLI 入口點 (cpack 命令)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── archiver.py     # 核心封存邏輯，協調整個流程
│       │   ├── extractor.py    # 解壓縮邏輯，支援多種格式
│       │   ├── verifier.py     # 完整性驗證邏輯 (5層驗證)
│       │   └── repairer.py     # PAR2 修復邏輯
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── compression.py  # Zstd 壓縮工具和參數最佳化
│       │   ├── hashing.py      # SHA-256 + BLAKE3 雜湊工具
│       │   ├── par2.py         # PAR2 冗餘工具 (subprocess 包裝)
│       │   ├── filesystem.py   # 檔案系統操作和安全管理
│       │   └── progress.py     # Rich 進度顯示和統計報告
│       └── config/
│           ├── __init__.py
│           ├── settings.py     # Pydantic 設定管理
│           └── constants.py    # 常數定義和預設值
├── tests/                      # Pytest 測試套件
│   ├── __init__.py
│   ├── test_archiver.py       # 核心封存邏輯測試
│   ├── test_extractor.py      # 解壓縮邏輯測試
│   ├── test_verifier.py       # 驗證邏輯測試
│   ├── test_utils.py          # 工具函數測試
│   └── fixtures/              # 測試資料和模擬檔案
├── docs/                      # 文件
│   ├── CLI_REFERENCE.md       # CLI 命令參考
│   └── EXAMPLES.md           # 使用範例
├── pyproject.toml            # 專案配置 (uv 管理)
├── CHANGELOG.md              # 版本變更紀錄
└── README.md                 # 使用者文件
```

### Known Gotchas of our codebase & Library Quirks
```python
# CRITICAL: py7zz 是現有的 Python 7-zip 包裝器 (版本 0.1.1+)
# 支援 50+ 種壓縮格式，包含 async 操作和進度報告
# GitHub: https://github.com/rxchi1d/py7zz
# 使用類似 zipfile 的 API 介面

# CRITICAL: zstandard 需要重用 compressor/decompressor 實例
# 每次操作都創建新實例會影響效能
cctx = zstandard.ZstdCompressor(level=19, long_distance_matching=True)
# 重用此實例進行多次壓縮操作

# CRITICAL: BLAKE3 支援串流處理大檔案
# 避免將整個檔案載入記憶體
hasher = blake3.blake3()
hasher.update(chunk)  # 分塊處理

# CRITICAL: Typer 使用 type hints 自動驗證
# 所有 CLI 參數必須有適當的類型註解
def archive(source: Path, output: Optional[Path] = None) -> None:

# CRITICAL: Rich Progress 需要 context manager 或手動 refresh
with Progress() as progress:
    task = progress.add_task("Processing...", total=100)
    # 更新進度

# CRITICAL: 臨時檔案管理使用 tempfile 模組
# 避免在系統臨時目錄留下垃圾檔案
with tempfile.TemporaryDirectory() as temp_dir:
    # 安全的臨時檔案操作

# CRITICAL: PAR2 依賴外部工具 par2cmdline
# 需要檢查工具可用性並提供清晰錯誤訊息
```

## Implementation Blueprint

### Data models and structure

創建核心資料模型，確保類型安全和一致性：

```python
# config/settings.py - Pydantic 設定模型
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional

class CompressionSettings(BaseModel):
    level: int = Field(default=19, ge=1, le=22)
    threads: int = Field(default=0, ge=0)
    long_mode: bool = True
    ultra_mode: bool = False

class ArchiveMetadata(BaseModel):
    source_path: Path
    archive_path: Path
    compression_settings: CompressionSettings
    created_at: str
    file_count: int
    original_size: int
    compressed_size: int
    compression_ratio: float
    verification_hashes: dict

# core/models.py - 業務邏輯模型
from enum import Enum
from dataclasses import dataclass

class OperationType(Enum):
    ARCHIVE = "archive"
    EXTRACT = "extract"
    VERIFY = "verify"
    REPAIR = "repair"
    INFO = "info"

@dataclass
class ProcessingStats:
    start_time: float
    end_time: float
    bytes_processed: int
    files_processed: int
    success: bool
    error_message: Optional[str] = None
```

### List of tasks to be completed to fulfill the PRP in the order they should be completed

```yaml
Task 1: 專案結構初始化
CREATE pyproject.toml:
  - MIRROR pattern from: examples/pyproject.toml
  - MODIFY dependencies for coldpack specific needs
  - KEEP development workflow identical

CREATE src/coldpack/__init__.py:
  - EXPORT main API functions and version
  - FOLLOW pattern from examples/CLAUDE.md versioning

CREATE src/coldpack/config/:
  - settings.py: Pydantic 設定模型
  - constants.py: 常數定義

Task 2: 核心工具模組實現
CREATE src/coldpack/utils/filesystem.py:
  - IMPLEMENT safe temporary file management
  - INCLUDE disk space checking utilities
  - MIRROR error handling patterns from archive-compress.sh

CREATE src/coldpack/utils/compression.py:
  - IMPLEMENT zstandard wrapper with dynamic parameters
  - INCLUDE compression level and thread optimization
  - PRESERVE memory efficiency for large files

CREATE src/coldpack/utils/hashing.py:
  - IMPLEMENT dual hash system (SHA-256 + BLAKE3)
  - INCLUDE streaming hash for large files
  - FOLLOW verification patterns from shell script

CREATE src/coldpack/utils/par2.py:
  - IMPLEMENT PAR2 subprocess wrapper
  - INCLUDE error handling and validation
  - MAINTAIN 10% redundancy default

CREATE src/coldpack/utils/progress.py:
  - IMPLEMENT Rich progress display system
  - INCLUDE multi-task progress tracking
  - MIRROR output patterns from shell script

Task 3: 核心業務邏輯
CREATE src/coldpack/core/extractor.py:
  - IMPLEMENT multi-format extraction using py7zz (SevenZipFile API)
  - INCLUDE intelligent directory structure detection
  - PRESERVE extraction logic from archive-compress.sh
  - UTILIZE py7zz async operations for large files

CREATE src/coldpack/core/archiver.py:
  - IMPLEMENT main archiving pipeline
  - COORDINATE all processing steps
  - INCLUDE 5-layer verification system

CREATE src/coldpack/core/verifier.py:
  - IMPLEMENT comprehensive verification system
  - INCLUDE tar header, zstd, hash, PAR2 checks
  - PRESERVE verification sequence from shell script

CREATE src/coldpack/core/repairer.py:
  - IMPLEMENT PAR2 repair functionality
  - INCLUDE damage assessment and recovery
  - MAINTAIN error reporting consistency

Task 4: CLI 介面實現
CREATE src/coldpack/cli.py:
  - IMPLEMENT Typer-based CLI with all commands
  - INCLUDE cpack archive/extract/verify/repair/info
  - FOLLOW CLI patterns from examples and best practices
  - PRESERVE option naming from shell script

Task 5: 測試套件建立
CREATE tests/ directory structure:
  - IMPLEMENT comprehensive unit tests for all modules
  - INCLUDE integration tests for full workflows
  - CREATE fixtures for test data
  - MAINTAIN test coverage ≥ 90%

Task 6: 文件和範例
CREATE documentation:
  - README.md: 使用者指南
  - docs/CLI_REFERENCE.md: 完整 CLI 參考
  - docs/EXAMPLES.md: 實際使用範例
  - CHANGELOG.md: 版本變更記錄
```

### Per task pseudocode as needed added to each task

```python
# Task 2: compression.py 核心實現
class ZstdCompressor:
    def __init__(self, level: int = 19, threads: int = 0, long_mode: bool = True):
        # PATTERN: 重用 compressor 實例提升效能
        self.cctx = zstandard.ZstdCompressor(
            level=level,
            threads=threads,
            long_distance_matching=long_mode
        )

    def compress_file(self, input_path: Path, output_path: Path) -> None:
        # CRITICAL: 使用串流處理避免記憶體問題
        with open(input_path, 'rb') as ifh, open(output_path, 'wb') as ofh:
            self.cctx.copy_stream(ifh, ofh)

# Task 3: extractor.py 使用 py7zz API
import py7zz
from pathlib import Path

class MultiFormatExtractor:
    def extract(self, source: Path, temp_dir: Path) -> Path:
        # PATTERN: 使用 py7zz 的 SevenZipFile API (類似 zipfile)
        if source.suffix.lower() in ['.7z', '.zip', '.rar', '.tar.gz']:
            with py7zz.SevenZipFile(source, 'r') as archive:
                # 智能目錄結構檢測
                files = archive.namelist()
                has_single_root = self._check_single_root_directory(files)

                if has_single_root:
                    # 直接解壓縮
                    archive.extractall(temp_dir)
                    return temp_dir / files[0].split('/')[0]
                else:
                    # 建立同名資料夾
                    target_dir = temp_dir / source.stem
                    target_dir.mkdir()
                    archive.extractall(target_dir)
                    return target_dir
        else:
            # 處理資料夾
            return source

# Task 3: archiver.py 主要邏輯
class ColdStorageArchiver:
    def create_archive(self, source: Path, output_dir: Path) -> ArchiveResult:
        # PATTERN: 遵循 shell script 的 5 層驗證流程
        with self.progress.track("Creating archive") as task:
            # 1. 解壓縮和結構檢查
            extracted_dir = self.extractor.extract(source, self.temp_dir)

            # 2. TAR 建立和驗證
            tar_path = self._create_deterministic_tar(extracted_dir)
            self.verifier.verify_tar_header(tar_path)

            # 3. Zstd 壓縮和驗證
            zst_path = self.compressor.compress(tar_path, output_dir)
            self.verifier.verify_zstd_integrity(zst_path)

            # 4. 雙重雜湊生成和驗證
            hashes = self.hasher.generate_dual_hashes(zst_path)
            self.verifier.verify_dual_hashes(zst_path, hashes)

            # 5. PAR2 生成和驗證
            par2_files = self.par2.generate_recovery(zst_path)
            self.verifier.verify_par2(zst_path, par2_files)

            return ArchiveResult(success=True, files=all_files)

# Task 4: cli.py CLI 實現
app = typer.Typer(help="Coldpack - Cross-platform cold storage archiver")

@app.command()
def archive(
    source: Path = typer.Argument(..., help="Source file or directory"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory"),
    level: int = typer.Option(19, "-l", "--level", min=1, max=22, help="Compression level"),
    threads: int = typer.Option(0, "-t", "--threads", min=0, help="Number of threads"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output")
) -> None:
    """Create a cold storage archive from source."""
    # PATTERN: 使用 Rich 顯示美觀的進度和結果
    # CRITICAL: 所有錯誤都要有清晰的使用者訊息
    try:
        archiver = ColdStorageArchiver(level=level, threads=threads)
        result = archiver.create_archive(source, output or Path.cwd())

        if result.success:
            console.print("[green]Archive created successfully![/green]")
            # 顯示統計資訊
        else:
            console.print(f"[red]Archive creation failed: {result.error}[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
```

### Integration Points
```yaml
EXTERNAL_TOOLS:
  - dependency: par2cmdline-turbo
    check: "par2 --help"
    install_hint: "sudo apt install par2cmdline 或 brew install par2"

  - dependency: system tar
    check: "tar --help | grep -E '(posix|gnu)'"
    requirement: "支援 POSIX 或 GNU 格式處理大檔案"

PYTHON_DEPENDENCIES:
  - py7zz>=0.1.1: 多格式壓縮/解壓縮，支援 async 和 progress callbacks
  - zstandard: 高效壓縮
  - blake3: 現代雜湊演算法
  - typer: 現代 CLI 框架
  - rich: 美觀終端輸出
  - pydantic: 資料驗證
  - loguru: 結構化日誌

CONFIG_FILES:
  - pyproject.toml: uv 專案配置
  - CLAUDE.md: 開發規範 (zh-tw)
  - README.md: 使用者文件 (zh-tw)
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff format .         # 自動格式化
uv run ruff check --fix .    # 風格檢查並自動修正
uv run mypy src/             # 類型檢查

# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests each new feature/file/function use existing test patterns
```python
# CREATE comprehensive test suite:
def test_archiver_happy_path():
    """基本封存功能正常運作"""
    archiver = ColdStorageArchiver()
    result = archiver.create_archive(test_folder, output_dir)
    assert result.success
    assert all(f.exists() for f in result.files)

def test_archiver_invalid_input():
    """無效輸入時正確處理錯誤"""
    archiver = ColdStorageArchiver()
    with pytest.raises(FileNotFoundError):
        archiver.create_archive(Path("nonexistent"), output_dir)

def test_verification_failure_handling():
    """驗證失敗時的錯誤處理"""
    # 模擬損壞的檔案
    corrupted_file = create_corrupted_test_file()
    verifier = Verifier()
    result = verifier.verify_integrity(corrupted_file)
    assert not result.success
    assert "corruption detected" in result.error_message

def test_cli_commands():
    """CLI 命令正確執行"""
    result = runner.invoke(app, ["archive", str(test_source), "-o", str(output_dir)])
    assert result.exit_code == 0
    assert "Archive created successfully" in result.output
```

```bash
# Run and iterate until passing:
uv run pytest -v --cov=src/coldpack --cov-report=html
# If failing: Read error, understand root cause, fix code, re-run
# Target: Coverage ≥ 90%
```

### Level 3: Integration Test
```bash
# Test real file processing
uv run pytest tests/integration/ -v

# Test CLI integration
cpack archive test_data/sample.7z -o output/ -v
cpack verify output/sample/sample.tar.zst
cpack info output/sample/sample.tar.zst

# Expected: All operations complete successfully with proper file outputs
# Check: tar.zst, .sha256, .blake3, .par2 files all present and valid
```

## Final validation Checklist
- [ ] All tests pass: `uv run pytest tests/ -v --cov=src/coldpack`
- [ ] No linting errors: `uv run ruff check src/`
- [ ] No type errors: `uv run mypy src/`
- [ ] CLI commands work: `cpack --help`, `cpack archive --help`
- [ ] Integration test successful: Create and verify real archive
- [ ] Error cases handled gracefully with clear messages
- [ ] Progress display works correctly for large files
- [ ] Cross-platform compatibility verified (Windows/macOS/Linux)
- [ ] Memory usage reasonable for large files (streaming processing)
- [ ] All dependencies properly declared in pyproject.toml
- [ ] Documentation complete and accurate

---

## Anti-Patterns to Avoid
- ❌ Don't load entire files into memory - use streaming
- ❌ Don't create new compressor instances for each operation
- ❌ Don't ignore verification failures - always abort on errors
- ❌ Don't use absolute paths in tar archives - maintain portability
- ❌ Don't skip error handling - every operation can fail
- ❌ Don't hardcode paths or assume specific operating systems
- ❌ Don't use shell=True in subprocess calls - security risk
- ❌ Don't forget to clean up temporary files in error cases

## Confidence Level Assessment
**Score: 9/10** - Very high confidence for successful one-pass implementation

**Strengths:**
- Comprehensive context from existing shell script implementation
- Well-established Python libraries with good documentation
- Clear project structure based on proven patterns
- Detailed validation steps and error handling guidance
- py7zz is confirmed existing package with async support and progress callbacks
- Complete API reference and usage patterns available

**Potential Challenges:**
- Cross-platform PAR2 tool availability may vary
- Large file handling needs careful memory management
- CLI UX design requires iteration based on user feedback

The extensive context provided, combined with the reference implementation in shell script form, provides strong foundation for successful implementation in a single development cycle.
