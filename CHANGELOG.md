# Changelog

All notable changes to this project will be documented in this file.

## [2.2.1] - 2026-04-15

### Fixed
- Parser-aware output handling for `.docx`, `.xlsx`, `.pptx`, and extracted `.pdf` text in batch mode and Flask Web UI, avoiding corrupted downloads with mismatched extensions
- Web UI download registry so single-file download and `download-all` always serve the actual processed artifact with stable anonymized filenames
- Claude Code hook mapping flow now restores tokens using the real session id instead of a hard-coded hook session
- Bash path protection now blocks indirect reads of protected scan paths instead of only a narrow set of file-reader commands
- OCR pipeline now uses `pytesseract.Output.DICT`, restoring text-in-image detection outside mocked tests
- Config export now normalizes absolute logo template paths inside `config.json` while still bundling the referenced logo files

## [2.2.0] - 2026-04-04

### Added
- Complete Claude Code hook setup instructions in both READMEs (settings.json configuration)
- Image anonymization prerequisites: Tesseract install guide, DNN model download instructions
- Missing Python dependencies in requirements.txt: Pillow, opencv-python, pytesseract
- Batch path validation: blocks system-sensitive directories (/etc, ~/.ssh, ~/.claude, etc.)
- Upload file size limit (100MB) for Web UI security

### Changed
- Auto-shutdown timeout extended from 120s to 600s (frontend health check serves as keep-alive)
- Architecture diagram updated: tkinter → Flask Web UI (both READMEs)
- GUI launch command corrected: `gui/app.py` → `gui/web_app.py`
- Project structure listing updated to reflect current file layout
- Test count updated: 168 → 175

### Fixed
- Config schema mismatch: `setup.py` now outputs `version` and `logo_templates` fields matching `config_manager.validate_config()` requirements
- `config_manager.validate_config()` now accepts optional fields from setup wizard (scan_paths, persist_mapping, etc.) without rejecting them
- License updated from "Private repository" to CC BY-NC 4.0

## [2.1.0] - 2026-03-29

### Added
- Flask Web UI replacing tkinter: drag-and-drop upload, Before/After preview, SSE progress streaming
- Design system (`DESIGN.md`): Teal theme, DM Sans + Noto Sans TC typography, PII category colors
- Embedded fonts (DM Sans, Noto Sans TC, Geist Mono) for offline use
- Download button and batch processing via Web UI
- Config import/export API endpoints
- Full-flow integration test for Web UI
- Server lifecycle management: auto-open browser, auto-shutdown on idle

### Changed
- Removed tkinter GUI dependency in favor of Flask + HTML/CSS/JS
- Updated PyInstaller spec for Web UI entry point and static files
- Updated CI workflow to include Flask dependency
- Extracted shared SSE parser, removed duplicate code

## [2.0.0] - 2026-03-26

### Added
- 3-stage image anonymization pipeline (OCR text PII + face detection + logo template matching)
- Image file parser (PIL-based with Tesseract OCR)
- Irreversible anonymization mode (`[CATEGORY]` tokens, non-reversible)
- GUI desktop application (tkinter) with file selection, drag-and-drop, batch processing, Before/After preview
- Batch processing module for folder-level anonymization
- Config manager with export/import as `.zip` (includes logo templates)
- Per-school config zips for 149 universities
- Windows distribution: portable zip + PyInstaller + Inno Setup installer
- GitHub Actions CI for automated Windows builds (Full + Lite)

### Changed
- Extracted shared detectors module, fixed DRY violations
- Switched to portable zip distribution (no install required)

### Fixed
- Bundle ckip NER model in Full build to fix httpx client error
- Windows cross-platform support (fcntl, temp paths, chmod)
- PyInstaller SPECPATH issue on GitHub Actions
- Tesseract download URL corrected to v5.4.0.20240606
- Chocolatey-based Tesseract installation replacing NSIS silent install

## [1.0.0] - 2026-03-25

### Added
- Core anonymizer engine with span-based pipeline
- Three-layer detection: custom terms (substring match) → regex (email, phone, ID, URL) → NER (ckip-transformers)
- Span model with overlap resolver (length-priority, source-priority)
- Token mapping manager with save/load/restore
- File parsers for `.txt`, `.md`, `.docx`, `.xlsx`, `.pptx`, `.pdf`
- Claude Code hook integration: PreToolUse interception (`hook_router.py`) and PostToolUse token reversal (`restore.py`)
- Interactive setup wizard (`setup.py`)
- Learned terms manager for uncertain span handling
- Persistent mapping support across sessions
- Temp file cleanup mode (`--cleanup`)
- E2E integration tests for complete hook pipeline

### Fixed
- Internal file protection narrowed to config/mappings only (source code accessible for development)
- Config and learned_terms files added to `.gitignore`

## [0.1.0] - 2026-03-25

### Added
- Project scaffold with dependency specification
- Initial `requirements.txt` (ckip-transformers, torch, transformers, python-docx, python-pptx, openpyxl, pdfplumber, pytest)

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|-----------|
| 2.2.1 | 2026-04-15 | Output path fixes, hook restore/session fix, OCR repair, config export normalization |
| 2.2.0 | 2026-04-04 | Security hardening, docs overhaul, config schema fix, CC BY-NC 4.0 |
| 2.1.0 | 2026-03-29 | Web UI (Flask), design system, embedded fonts |
| 2.0.0 | 2026-03-26 | Image anonymization, GUI, batch processing, Windows distribution |
| 1.0.0 | 2026-03-25 | Core engine, 3-layer detection, hook integration, file parsers |
| 0.1.0 | 2026-03-25 | Project scaffold |
