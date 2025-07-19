## FEATURE:

我要設計一個跨平台的冷儲存 Python CLI 套件，專門用於將指定的來源檔案或資料夾封存成標準化的冷儲存格式。套件名稱為 `coldpack`，CLI 命令名稱使用 `cpack`。

**核心功能:**
- 將各種來源（資料夾、7z、zip、tar.gz 等）轉換為統一的 `tar.zst` 格式
- 產生完整的冷儲存檔案組，包含雙重雜湊驗證和修復冗餘
- 支援解壓縮、驗證和檔案修復功能
- 提供詳細的統計報告和進度顯示

**處理流程:**
1. **來源分析與解壓縮**
   - 檢查來源類型（資料夾或壓縮檔案）
   - 使用 `py7zz` 套件處理多種壓縮格式（7z、zip、rar、tar.gz 等）
   - 智能目錄結構檢測：自動處理單層資料夾問題
   - 統一輸出結構至臨時目錄

2. **TAR 封存**
   - 使用 `--sort=name` 參數確保 deterministic 排序
   - POSIX 格式優先，支援大檔案處理
   - 立即進行 tar header 驗證

3. **Zstandard 壓縮**
   - 動態調整窗口尺寸（根據檔案大小決定 `--long` 參數）
   - 動態調整壓縮等級（預設 -19，支援 ultra 模式）
   - 多核心並行處理
   - 內建完整性檢查 (`--check`)
   - 參數記錄至 metadata.toml

4. **雙重雜湊生成**
   - SHA-256（使用 `hashlib`）
   - BLAKE3（使用 `blake3` 套件）
   - 分步驟生成並即時驗證

5. **PAR2 修復冗餘**
   - 使用 `par2cmdline-turbo` 支援多核心
   - 預設 10% 冗餘率，可調整
   - 限制輸出檔案數量（`-n1`）

6. **完整性驗證**
   - 5層驗證機制確保每步驟成功
   - 失敗重試機制（有次數限制）
   - 詳細錯誤報告和診斷資訊

**輸出結構:**
```
output-dir/
├─ source_name/
│  ├─ source_name.tar.zst
│  ├─ metadata/
│  │  ├─ source_name.tar.zst.sha256
│  │  ├─ source_name.tar.zst.blake3
│  │  ├─ source_name.tar.zst.par2
│  │  ├─ source_name.tar.zst.vol000+XXX.par2
│  │  └─ source_name.tar.zst.toml
```

**CLI 功能:**
- `cpack archive`: 建立冷儲存封存
- `cpack extract`: 解壓縮封存檔案
- `cpack verify`: 驗證檔案完整性
- `cpack repair`: 使用 PAR2 修復損壞檔案
- `cpack info`: 顯示封存檔案資訊

**技術特色:**
- 磁碟空間預檢機制
- 安全的臨時檔案管理
- 漂亮的進度顯示和統計報告
- 跨平台兼容性（Windows、macOS、Linux）
- 支援 `--verbose`、`--quiet`、`--force` 等常用選項
- 動態系統規格檢測和參數最佳化

## EXAMPLES:

- `examples/CLAUDE.md`: 參考的開發規範和工具配置
- `examples/pyproject.toml`: 專案配置參考，包含開發依賴和工具設定
- `examples/VERSION_STRATEGY.md`: PEP 440 版本控制策略
- `examples/archive-compress.sh`: Bash 腳本實現參考，瞭解詳細處理流程
- `examples/API.md`: py7zz 套件 API 文檔參考

## DOCUMENTATION:

### 專案結構設計
```
coldpack/
├── src/
│   └── coldpack/
│       ├── __init__.py
│       ├── cli.py              # CLI 入口點 (cpack)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── archiver.py     # 核心封存邏輯
│       │   ├── extractor.py    # 解壓縮邏輯
│       │   ├── verifier.py     # 驗證邏輯
│       │   └── repairer.py     # 修復邏輯
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── compression.py  # Zstd 壓縮工具
│       │   ├── hashing.py      # 雜湊工具
│       │   ├── par2.py         # PAR2 工具
│       │   ├── filesystem.py   # 檔案系統工具
│       │   └── progress.py     # 進度顯示
│       └── config/
│           ├── __init__.py
│           ├── settings.py     # 設定管理
│           └── constants.py    # 常數定義
├── tests/
│   ├── __init__.py
│   ├── test_archiver.py
│   ├── test_extractor.py
│   ├── test_verifier.py
│   ├── test_utils.py
│   └── fixtures/               # 測試資料
├── docs/
│   ├── README.md
│   ├── CLI_REFERENCE.md
│   └── EXAMPLES.md
├── pyproject.toml
├── README.md
├── CLAUDE.md
└── CHANGELOG.md
```

### 相依套件
```toml
dependencies = [
    "py7zz",          # 多格式壓縮解壓縮
    "zstandard",      # Zstd 壓縮
    "blake3",         # BLAKE3 雜湊
    "typer",          # CLI 框架
    "rich",           # 美化輸出
    "pydantic",       # 資料驗證
    "toml",           # TOML 配置
    "loguru",         # 日誌管理
    "python-dotenv",  # 環境變數管理
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "mypy",
    "ruff",
]
```

## OTHER CONSIDERATIONS:

1. **繼承 examples/CLAUDE.md 的規範:**
   - 語言規則：CLAUDE.md 等開發用文件使用 zh-tw，程式碼註解與發布用文件使用 en
   - 環境與套件管理使用 `uv`
   - 完整的開發工作流程和品質檢查
   - 提交訊息規範和 PR 標準

2. **專案特色:**
   - 單一檔案不超過 500 行，模組化設計
   - 完整的 Pytest 單元測試覆蓋
   - Google 格式的 docstring
   - 使用 `python_dotenv` 和 `load_env()`
   - 遵循 PEP8 和類型註解標準

3. **安全與穩定性:**
   - 所有檔案操作都有錯誤處理
   - 臨時檔案安全管理機制（使用套件內部設計，不依賴環境變數）
   - 磁碟空間預檢和系統資源監控
   - 多層驗證確保資料完整性

4. **使用者體驗:**
   - 清晰的進度顯示和統計報告
   - 詳細的錯誤訊息和解決建議
   - 支援 verbose 和 quiet 模式
   - 跨平台一致的操作體驗

5. **效能最佳化:**
   - 多核心並行處理
   - 動態參數調整
   - 記憶體使用量監控
   - 快取機制避免重複計算

`coldpack` 旨在成為標準化的冷儲存解決方案，提供簡潔易用的 `cpack` 命令，確保長期資料保存的安全性和可靠性。