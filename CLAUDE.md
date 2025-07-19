# CLAUDE.md

此檔案提供 Claude Code (claude.ai/code) 在此儲存庫中工作時的指引。

## 語言規則

**重要：請嚴格遵循以下語言規則**

1. **Claude.md 內容**：使用zh-tw
2. **與 Claude 對話**：使用zh-tw
3. **PRP文件等開發過程中使用的文件**：使用zh-tw
4. **程式碼註解**：使用en
5. **函數/變數命名**：使用en
6. **Git commit 訊息**：使用en
7. **文件字串 (docstrings)**：使用en
8. **其他發布用文件**：使用en

## 專案概述

coldpack 是一個 Python CLI 套件，專門用於建立標準化的冷儲存封存檔案。它將各種來源（資料夾、7z、zip、tar.gz 等）轉換為統一的 tar.zst 格式，並提供雙重雜湊驗證、PAR2 修復冗餘等完整的長期保存功能。

**Python 支援版本**：Python 3.8+ (包含 Python 3.13)

**專案願景**：提供一個可靠、標準化的冷儲存解決方案，透過簡潔的 `cpack` 命令確保重要資料的長期保存安全性，支援跨平台使用且具備完整的驗證和修復機制。

## 開發命令

### 環境設定
```bash
# 使用 uv 建立虛擬環境
uv venv .venv

# 啟動虛擬環境（在執行任何工具時必須使用）
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 安裝方法

#### 開發安裝
```bash
# 複製儲存庫並安裝開發依賴
git clone <repository-url>
cd coldpack
uv sync --dev
```

### 依賴管理
**重要**：所有依賴必須透過 `uv add` 命令管理。禁止手動編輯 `pyproject.toml` 或使用 `pip install`。

```bash
# 執行期依賴
uv add py7zz zstandard blake3 typer rich pydantic loguru

# 開發依賴
uv add --dev pytest pytest-cov mypy ruff
```

### 核心開發循環
```bash
# 使用 uv（推薦）
uv run ruff check --fix .   # 風格檢查並自動修正
uv run ruff format .        # 格式化程式碼
uv run mypy src/            # 類型檢查
uv run pytest              # 執行單元測試
```

**注意**：完整的程式碼品質檢查會在 GitHub Actions 中執行，確保 PR 合併前的程式碼品質。

### 完整開發工作流程範例
```bash
# 1. 啟動開發環境
source .venv/bin/activate

# 2. 開發程式碼...

# 3. 執行完整質檢流程（與 CI 一致）
uv run ruff format .        # 格式化程式碼
uv run ruff check --fix .   # 檢查並修正程式碼風格
uv run mypy src/            # 類型檢查
uv run pytest              # 執行完整測試套件

# 4. 確認所有檢查通過後才提交
git add .
git commit -m "feat: add cold storage archiving functionality"

# 5. 推送前再次確認 CI 會通過
git push origin <branch-name>
```

## 架構

### 專案結構
```
coldpack/
├── src/
│   └── coldpack/
│       ├── __init__.py         # 匯出主要 API
│       ├── cli.py              # CLI 入口點（Typer）
│       ├── core/
│       │   ├── __init__.py
│       │   ├── archiver.py     # 核心封存邏輯
│       │   ├── extractor.py    # 解壓縮邏輯
│       │   ├── verifier.py     # 驗證邏輯
│       │   └── repairer.py     # PAR2 修復邏輯
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── compression.py  # Zstd 壓縮工具
│       │   ├── hashing.py      # SHA-256 + BLAKE3 雜湊
│       │   ├── par2.py         # PAR2 冗餘工具
│       │   ├── filesystem.py   # 檔案系統操作
│       │   └── progress.py     # 進度顯示（Rich）
│       └── config/
│           ├── __init__.py
│           ├── settings.py     # 設定管理
│           └── constants.py    # 常數定義
├── tests/                      # 測試套件
│   ├── __init__.py
│   ├── test_archiver.py
│   ├── test_extractor.py
│   ├── test_verifier.py
│   ├── test_utils.py
│   └── fixtures/               # 測試資料
├── docs/                       # 文件
│   ├── README.md
│   ├── CLI_REFERENCE.md
│   └── EXAMPLES.md
├── pyproject.toml
├── README.md
├── CLAUDE.md                   # 此檔案
├── TASK.md                     # 任務追蹤
├── PLANNING.md                 # 專案規劃
└── CHANGELOG.md
```

### 核心元件
- **Archiver**：主要封存引擎，協調整個冷儲存流程
- **Extractor**：解壓縮引擎，支援多種格式（透過 py7zz）
- **Verifier**：完整性驗證引擎（tar header、zstd、雜湊、PAR2）
- **Repairer**：PAR2 修復引擎
- **CLI**：命令列介面（使用 Typer 框架，`cpack` 命令）
- **Progress**：進度顯示系統（使用 Rich）

### 處理流程架構
```
Input Source → py7zz Extraction → Temporary Directory
    ↓
TAR Creation (POSIX, sorted) → TAR Verification
    ↓
Zstd Compression (dynamic params) → Zstd Verification
    ↓
Dual Hash Generation (SHA-256 + BLAKE3) → Hash Verification
    ↓
PAR2 Redundancy Generation → PAR2 Verification
    ↓
Final Organization → Statistics Report
```

## CI/CD 流水線

### GitHub Actions 工作流程
1. **ci.yml**：push/PR 時執行 - ruff、mypy、pytest（PR 閘道）
   - 測試 Python 版本：3.8, 3.9, 3.10, 3.11, 3.12, 3.13
   - 測試作業系統：Ubuntu, macOS, Windows
2. **build.yml**：tag push 時觸發 - 建置和發布
3. **test-integration.yml**：整合測試（真實檔案測試）

### 程式碼品質要求
- **Ruff**：強制程式碼風格，line-length=88、select=["E", "F", "I", "UP", "B", "C4", "SIM"]
- **MyPy**：所有程式碼都需要類型檢查，target-version=py38
- **Pytest**：合併前單元測試必須通過，覆蓋率 ≥ 90%
- **CI 必須通過**：所有程式碼必須通過 GitHub Actions 中的完整檢查

## 程式碼提交前檢查清單

在提交程式碼前，請確保：
- [ ] `uv run ruff format .` 執行成功，程式碼格式化完成
- [ ] `uv run ruff check --fix .` 無錯誤，所有 lint 規則通過
- [ ] `uv run mypy src/` 無錯誤，所有類型檢查通過
- [ ] `uv run pytest` 全部測試通過，覆蓋率滿足要求
- [ ] 所有新功能都有對應的單元測試
- [ ] 相關文件已同步更新（README.md、CLI_REFERENCE.md）
- [ ] 程式碼符合專案架構和設計原則
- [ ] 沒有遺留的 TODO 或 FIXME 註解（除非有計劃處理）
- [ ] 提交訊息遵循約定格式

## 提交訊息規範

coldpack 遵循**約定式提交**（Conventional Commits）規範。

### 格式要求
```
<type>(<scope>): <description>    ← 第一行（50-72 字符）

[optional body]                   ← 說明（72 字符換行）

[optional footer(s)]              ← 破壞性變更、問題參考
```

### 提交類型
- **feat**: 新功能（對應 MINOR 版本）
- **fix**: 錯誤修復（對應 PATCH 版本）
- **docs**: 文件變更
- **style**: 代碼格式（不影響功能）
- **refactor**: 重構代碼
- **perf**: 性能優化
- **test**: 測試相關
- **chore**: 建置或工具變更
- **ci**: CI/CD 相關

### 作用域示例
- **archiver**: 封存功能
- **extractor**: 解壓縮功能
- **verifier**: 驗證功能
- **cli**: 命令列介面
- **utils**: 工具函數
- **config**: 配置管理

### 範例
```bash
# 好的範例
git commit -m "feat(archiver): add dynamic zstd compression level adjustment"
git commit -m "fix(verifier): resolve blake3 hash verification on Windows"
git commit -m "docs(cli): add complete CLI reference with examples"

# 複雜變更的多行範例
git commit -m "feat(archiver): implement parallel processing for large archives

This commit adds comprehensive parallel processing support including:
- Multi-threaded compression using all available CPU cores
- Memory usage optimization for large files
- Progress tracking across multiple operations
- Cross-platform compatibility testing

The implementation maintains backward compatibility while
providing significant performance improvements for archives > 1GB."
```

## 開發注意事項

### 模組化設計原則
- **單一檔案不得超過 500 行程式碼**
- **每個模組都有清楚的職責分工**
- **使用相對匯入** (`from .utils import compression`)
- **每個函式都需要 Google 格式的 docstring**

### 測試要求
- **為所有新功能撰寫 Pytest 單元測試**
- **至少包含：正常情境、邊界情況、失敗情況**
- **測試應位於 `/tests` 資料夾中**
- **使用 fixtures 提供測試資料**

### 錯誤處理
- **所有檔案操作都要有適當的錯誤處理**
- **使用具體的例外類型而非通用 Exception**
- **提供有用的錯誤訊息和解決建議**
- **記錄重要操作的日誌資訊**

### 效能考量
- **大檔案處理要支援進度顯示**
- **使用多核心處理（當相關套件支援時）**
- **監控記憶體使用量**
- **提供磁碟空間預檢機制**

## 冷儲存功能特殊要求

### 可重現性
- **使用 deterministic tar 建立** (`--sort=name`)
- **記錄所有壓縮參數** (存於 .toml)
- **確保跨平台一致性**

### 完整性保證
- **5層驗證機制**：tar header → zstd → SHA-256 → BLAKE3 → PAR2
- **失敗重試機制**（有次數限制）
- **詳細的診斷資訊**

### 長期保存
- **雙重雜湊演算法** (SHA-256 + BLAKE3)
- **PAR2 修復冗餘** (預設 10%)
- **標準化輸出格式**

## 相依套件說明

### 核心相依套件
- **py7zz**: 多格式壓縮解壓縮（7z、zip、rar 等）
- **zstandard**: Zstd 壓縮，高效能現代壓縮演算法
- **blake3**: BLAKE3 雜湊演算法，現代密碼學雜湊
- **typer**: 現代 Python CLI 框架
- **rich**: 美化終端輸出和進度顯示
- **pydantic**: 資料驗證和設定管理
- **loguru**: 現代日誌管理

### 外部工具相依
- **tar**: 系統 tar 工具（POSIX/GNU 格式支援）
- **par2cmdline-turbo**: PAR2 修復檔案工具

## 安全性考量

### 檔案安全
- **臨時檔案使用安全的路徑**
- **處理完成後立即清理臨時檔案**
- **避免路徑注入攻擊**
- **檢查檔案權限**

### 資料完整性
- **所有操作都有驗證步驟**
- **使用加密學等級的雜湊演算法**
- **支援檔案損壞修復**

coldpack 旨在成為標準化、可靠的冷儲存解決方案，透過 `cpack` 命令為重要資料的長期保存提供完整的保護機制。