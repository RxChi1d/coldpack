# coldpack

[![PyPI version](https://badge.fury.io/py/coldpack.svg)](https://badge.fury.io/py/coldpack)
[![Python Support](https://img.shields.io/pypi/pyversions/coldpack.svg)](https://pypi.org/project/coldpack/)
[![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/rxchi1d/coldpack)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI Status](https://github.com/rxchi1d/coldpack/workflows/CI/badge.svg)](https://github.com/rxchi1d/coldpack/actions)

[English](README.md) | [繁體中文](README.zh-tw.md)

> **專業級 7z 冷儲存解決方案與革命性架構**
>
> 進階 CLI 工具，用於建立標準化 7z 封存檔案，具備完整驗證、PAR2 修復與智慧跨平台相容性。

## 概述

coldpack 是一個專業級 CLI 工具，以其**7z 專屬架構**徹底革新冷儲存技術。專為長期資料保存而設計，能將各種封存格式轉換為標準化 7z 冷儲存格式，並提供完整的驗證與修復系統。

**核心創新**：完全重新設計的架構，專注於 7z 格式，提供業界最先進的冷儲存解決方案與 7 層動態壓縮最佳化。

## 特色功能

### 🚀 革命性 7z 專屬架構
- **專業 7z 單一輸出**：專門針對 7z 冷儲存最佳化的簡化架構
- **7 層動態壓縮**：智慧參數選擇（< 256KB 至 > 2GB 檔案大小）
- **簡化 CLI 介面**：無格式混亂 - 純 7z 冷儲存工作流程

### 🔧 完整 CLI 命令套件
- **`cpack create`** - 建立具動態最佳化的 7z 冷儲存
- **`cpack extract`** - 自動參數恢復與預驗證解壓縮
- **`cpack verify`** - 4 層完整性驗證與自動發現
- **`cpack repair`** - 基於 PAR2 的修復與中繼資料參數還原
- **`cpack info`** - 專業樹狀結構中繼資料顯示
- **`cpack list`** - 進階檔案列表與篩選及分頁功能

### 🛡️ 進階驗證與修復
- **4 層驗證系統**：7z 完整性 → SHA-256 → BLAKE3 → PAR2
- **雙重密碼學雜湊**：SHA-256 + BLAKE3 提供完整性保障
- **PAR2 修復檔案**：10% 冗餘度與多核心生成
- **參數持久化**：完整 metadata.toml 與自動參數恢復

### 🌐 跨平台卓越性
- **通用相容性**：Windows、macOS、Linux 完整 Unicode 支援
- **智慧系統檔案篩選**：自動排除 .DS_Store、Thumbs.db 等
- **Windows 檔名處理**：自動衝突解決與清理
- **專業日誌記錄**：結構化輸出與完整進度追蹤

詳細安裝與使用說明，請參見[安裝指南](docs/INSTALLATION.md)與 [CLI 參考](docs/CLI_REFERENCE.md)。

## 快速開始

### 安裝

```bash
# 使用 pip（推薦）
pip install coldpack

# 使用 uv
uv add coldpack
```

**系統需求**：Python 3.9+ | Windows、macOS、Linux

> **📋 詳細設定**：包含開發環境設定的完整安裝說明，請參見[安裝指南](docs/INSTALLATION.md)

### 基本使用

```bash
# 建立 7z 冷儲存封存
cpack create /path/to/documents --output-dir ~/cold-storage

# 自動參數恢復解壓縮
cpack extract ~/cold-storage/documents.7z --output-dir ~/restored

# 驗證 4 層完整性
cpack verify ~/cold-storage/documents.7z

# 進階檔案列表與篩選
cpack list ~/cold-storage/documents.7z --filter "*.pdf" --limit 10
```

### 專業功能

```bash
# 自訂壓縮等級（0-9）
cpack create large-dataset/ --level 9 --dict 512m --output-dir ~/archives

# 解壓縮前預驗證
cpack extract suspicious-archive.7z --verify --output-dir ~/safe-extraction

# 使用 PAR2 修復損壞檔案
cpack repair ~/cold-storage/damaged-archive.7z

# 專業中繼資料顯示
cpack info ~/cold-storage/documents.7z
```

> **📚 完整範例**：全面的使用案例與進階工作流程請見[使用範例](docs/EXAMPLES.md)。

## 技術規格

### 支援輸入格式
- **目錄**：任何檔案系統目錄結構
- **封存格式**：7z、zip、rar、tar、tar.gz、tar.bz2、tar.xz、tar.zst

### 專業 7z 輸出結構
```
archive-name/
├── archive-name.7z              # 主要 7z 封存
├── archive-name.7z.sha256       # SHA-256 雜湊
├── archive-name.7z.blake3       # BLAKE3 雜湊
├── archive-name.7z.par2         # PAR2 修復檔案
└── metadata/
    └── metadata.toml            # 完整封存中繼資料
```

### 4 層驗證系統

1. **🏗️ 7z 完整性**：原生 7z 封存結構驗證
2. **🔐 SHA-256**：密碼學雜湊驗證（向後相容性）
3. **⚡ BLAKE3**：現代高效能密碼學雜湊
4. **🛡️ PAR2 修復**：10% 冗餘度錯誤修正

### 7 層動態壓縮

| 檔案大小範圍 | 壓縮等級 | 字典大小 | 使用場景 |
|------------|---------|---------|---------|
| < 256 KiB | Level 1 | 128k | 最小資源消耗 |
| 256 KiB – 1 MiB | Level 3 | 1m | 輕量壓縮 |
| 1 – 8 MiB | Level 5 | 4m | 平衡效能 |
| 8 – 64 MiB | Level 6 | 16m | 良好壓縮 |
| 64 – 512 MiB | Level 7 | 64m | 高壓縮率 |
| 512 MiB – 2 GiB | Level 9 | 256m | 最大壓縮 |
| > 2 GiB | Level 9 | 512m | 極致壓縮 |

> **🔧 技術詳情**：架構文件與進階配置請見[架構指南](docs/ARCHITECTURE.md)

## 開發與貢獻

### 開發環境設定

```bash
# 複製並設定開發環境
git clone https://github.com/rxchi1d/coldpack.git
cd coldpack
uv sync --dev
source .venv/bin/activate
```

### 品質保證

```bash
# 程式碼格式化與檢查
uv run ruff format . && uv run ruff check --fix .

# 型別檢查與測試
uv run mypy src/ && uv run pytest
```

**開發標準**：134 個完整測試、ruff 格式化、MyPy 型別檢查、跨平台 CI/CD

> **🔨 開發指南**：[CLAUDE.md](CLAUDE.md) 中的完整開發說明

## 授權與支援

**授權**：MIT - 詳見 [LICENSE](LICENSE)

**文件**：
- 📖 [安裝指南](docs/INSTALLATION.md) - 完整設定說明
- 📋 [CLI 參考](docs/CLI_REFERENCE.md) - 完整命令文件
- 💡 [使用範例](docs/EXAMPLES.md) - 真實世界使用案例與工作流程
- 🏗️ [架構指南](docs/ARCHITECTURE.md) - 技術實作詳情

**支援**：[GitHub Issues](https://github.com/rxchi1d/coldpack/issues) | [討論區](https://github.com/rxchi1d/coldpack/discussions)

---

<div align="center">

**coldpack v0.1.0** - *專業級 7z 冷儲存解決方案*

*為可靠性而設計，為效能而最佳化，為未來而打造。*

</div>
