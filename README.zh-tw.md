<!--
SPDX-FileCopyrightText: 2025 coldpack contributors
SPDX-License-Identifier: MIT
-->

# coldpack

[![PyPI version](https://badge.fury.io/py/coldpack.svg)](https://badge.fury.io/py/coldpack)
[![Python Support](https://img.shields.io/pypi/pyversions/coldpack.svg)](https://pypi.org/project/coldpack/)
[![Platform Support](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/rxchi1d/coldpack)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI Status](https://github.com/rxchi1d/coldpack/workflows/CI/badge.svg)](https://github.com/rxchi1d/coldpack/actions)

[English](README.md) | [繁體中文](README.zh-tw.md)

用於建立標準化 7z 封存檔案的 Python CLI 工具，具備完整性驗證、PAR2 修復與跨平台相容性，專為長期資料儲存設計。

## 概述

coldpack 是一個用於建立標準化冷儲存封存檔案的指令列工具。它將各種來源格式（目錄、zip、tar 等）轉換為 7z 封存檔案，並整合了專為長期資料保存設計的驗證與修復機制。

## 特色功能

### 核心功能
- **7z 專屬輸出**：將各種輸入格式轉換為標準化 7z 封存檔案
- **適應性壓縮**：根據檔案大小自動選擇壓縮參數
- **指令列介面**：提供簡潔的 CLI 命令進行封存管理

### 可用命令
- **`cpack create`** - 建立 7z 冷儲存封存檔案
- **`cpack extract`** - 解壓縮封存檔案並還原參數
- **`cpack verify`** - 使用多種方法驗證封存完整性
- **`cpack repair`** - 使用 PAR2 修復損壞的封存檔案
- **`cpack info`** - 顯示封存中繼資料
- **`cpack list`** - 列出封存內容並提供篩選選項

### 驗證與修復
- **多層驗證機制**：7z 完整性、SHA-256、BLAKE3 與 PAR2
- **雙重雜湊演算法**：SHA-256 提供相容性，BLAKE3 提供效能
- **PAR2 修復檔案**：10% 冗餘度進行錯誤修正
- **中繼資料保存**：在 metadata.toml 中儲存壓縮參數

### 跨平台支援
- **作業系統**：Windows、macOS、Linux
- **系統檔案處理**：自動排除平台特定檔案（.DS_Store、Thumbs.db）
- **Unicode 支援**：正確處理國際化檔名
- **進度追蹤**：操作期間即時進度顯示

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

包含開發環境設定的詳細安裝說明，請參見[安裝指南](docs/INSTALLATION.md)。

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

### 進階使用

```bash
# 自訂壓縮等級（0-9）並設定記憶體限制
cpack create large-dataset/ --level 9 --dict 512m --memory-limit 2g --output-dir ~/archives

# 記憶體受限系統的壓縮
cpack create documents/ --memory-limit 512m --output-dir ~/archives

# 解壓縮前預驗證
cpack extract suspicious-archive.7z --verify --output-dir ~/safe-extraction

# 使用 PAR2 修復損壞檔案
cpack repair ~/cold-storage/damaged-archive.7z

# 中繼資料資訊顯示
cpack info ~/cold-storage/documents.7z
```

更多使用案例與工作流程請見[使用範例](docs/EXAMPLES.md)。

## 技術規格

### 支援輸入格式
- **目錄**：任何檔案系統目錄結構
- **封存格式**：7z、zip、rar、tar、tar.gz、tar.bz2、tar.xz、tar.zst

### 輸出結構
```
archive-name/
├── archive-name.7z              # 主要 7z 封存
├── archive-name.7z.sha256       # SHA-256 雜湊
├── archive-name.7z.blake3       # BLAKE3 雜湊
├── archive-name.7z.par2         # PAR2 修復檔案
└── metadata/
    └── metadata.toml            # 完整封存中繼資料
```

### 驗證系統

1. **7z 完整性**：原生 7z 封存結構驗證
2. **SHA-256**：密碼學雜湊驗證（向後相容性）
3. **BLAKE3**：現代高效能密碼學雜湊
4. **PAR2 修復**：10% 冗餘度錯誤修正

### 壓縮最佳化

| 檔案大小範圍 | 壓縮等級 | 字典大小 | 使用場景 |
|------------|---------|---------|---------|
| < 256 KiB | Level 1 | 128k | 最小資源消耗 |
| 256 KiB – 1 MiB | Level 3 | 1m | 輕量壓縮 |
| 1 – 8 MiB | Level 5 | 4m | 平衡效能 |
| 8 – 64 MiB | Level 6 | 16m | 良好壓縮 |
| 64 – 512 MiB | Level 7 | 64m | 高壓縮率 |
| 512 MiB – 2 GiB | Level 9 | 256m | 最大壓縮 |
| > 2 GiB | Level 9 | 512m | 最大效率 |

架構文件與詳細配置選項請見[架構指南](docs/ARCHITECTURE.md)。

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

**開發標準**：完整測試套件、ruff 格式化、MyPy 型別檢查、跨平台 CI/CD

完整開發說明請見 [CLAUDE.md](CLAUDE.md)。


## 授權與支援

**授權**：MIT - 詳見 [LICENSE](LICENSE)

**文件**：
- [安裝指南](docs/INSTALLATION.md) - 設定說明
- [CLI 參考](docs/CLI_REFERENCE.md) - 命令文件
- [使用範例](docs/EXAMPLES.md) - 使用案例與工作流程
- [架構指南](docs/ARCHITECTURE.md) - 技術實作詳情

**支援**：[GitHub Issues](https://github.com/rxchi1d/coldpack/issues) | [討論區](https://github.com/rxchi1d/coldpack/discussions)
