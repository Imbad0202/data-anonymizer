# Data Anonymizer

[中文版](README.md)

Automatically detect and anonymize personally identifiable information (PII) before sending data to AI tools. Supports text files, Office documents, PDFs, and images.

## Features

- **Text Anonymization** — Detect and replace names, phone numbers, national IDs, emails, school names, and more
- **Image Anonymization** — OCR text detection + face detection + logo template matching with automatic redaction
- **Dual Mode** — Pseudonymization (reversible, generates token mapping) / Anonymization (irreversible, compliant with Taiwan's Personal Data Protection Act)
- **Multi-format Support** — `.txt` `.md` `.docx` `.xlsx` `.pptx` `.pdf` `.jpg` `.png` `.bmp` `.tiff`
- **Three-layer Detection** — Custom terms → Regex patterns → NER (ckip-transformers, optimized for Traditional Chinese)
- **Web UI** — Flask local web interface with drag-and-drop upload / batch processing / Before/After preview / SSE progress streaming
- **Claude Code Hook** — Works as a PreToolUse hook for Claude Code, automatically intercepting and anonymizing sensitive files
- **Config Export/Import** — Bundle as `.zip` for one-click distribution to colleagues
- **Windows Installer** — PyInstaller packaging + Inno Setup installer, built automatically via GitHub Actions

## Architecture

```
                ┌─────────────────────────────────────────┐
                │           DATA ANONYMIZER v2             │
                ├─────────────────────────────────────────┤
                │  ┌──────────┐   ┌──────────────────┐   │
                │  │  Web UI  │   │  CLI / Hook Mode  │   │
                │  │ (Flask)  │   │ (Claude Code)     │   │
                │  └────┬─────┘   └──────┬───────────┘   │
                │       └───────┬────────┘               │
                │               ▼                        │
                │  ┌──────────────────────────┐          │
                │  │      Core Engine          │          │
                │  │  Text: custom→regex→NER   │          │
                │  │  Image: OCR→Face→Logo     │          │
                │  │  Mode: reversible / irreversible │   │
                │  └──────────────────────────┘          │
                └─────────────────────────────────────────┘
```

## Quick Start

### As a Claude Code Hook

```bash
# 1. Install
cd ~/.claude/anonymizer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Run setup wizard
.venv/bin/python setup.py

# 3. Configure Claude Code hooks (add to ~/.claude/settings.json)
```

Add the following to the `hooks` section of `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/anonymizer/.venv/bin/python ~/.claude/anonymizer/hook_router.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/anonymizer/.venv/bin/python ~/.claude/anonymizer/restore.py"
          }
        ]
      }
    ]
  }
}
```

Once configured, Claude Code will automatically anonymize files under `scan_paths` when reading, and restore tokens when writing.

### As a Web UI

```bash
# Development mode (auto-opens browser)
.venv/bin/python gui/web_app.py
```

Or download the Windows installer from [GitHub Releases](https://github.com/Imbad0202/data-anonymizer/releases).

### As a Python Module

```python
from anonymizer import Anonymizer

config = {
    "custom_terms": {"schools": ["National Taiwan University", "National Tsing Hua University"]},
    "substring_match": True,
}

# Pseudonymization (reversible)
anon = Anonymizer(config=config, session_id="demo", use_ner=False, reversible=True)
result, summary = anon.anonymize_text("John studies at National Taiwan University, phone 0912345678")
print(result)   # __ANON:PERSON_001__ studies at __ANON:SCHOOL_001__, phone __ANON:PHONE_001__

# Anonymization (irreversible)
anon = Anonymizer(config=config, session_id="demo", use_ner=False, reversible=False)
result, summary = anon.anonymize_text("John studies at National Taiwan University, phone 0912345678")
print(result)   # [PERSON] studies at [SCHOOL], phone [PHONE]
```

## Image Anonymization

### Prerequisites

Image anonymization requires additional system packages (not installable via `pip`):

```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-chi-tra

# Windows
# Download Tesseract installer: https://github.com/UB-Mannheim/tesseract/wiki
# Select "Chinese Traditional" language pack during installation
```

Download the face detection model to the `models/` directory:

```bash
mkdir -p models && cd models
curl -LO https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt
curl -LO https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel
```

### Three-stage pipeline

1. **OCR Text PII** — Tesseract OCR extracts text → existing detectors identify sensitive data → pixel coordinates mapped
2. **Face Detection** — OpenCV DNN (res10_300x300_ssd_iter_140000.caffemodel), CPU-only
3. **Logo Detection** — OpenCV matchTemplate with multi-scale search (0.5x–2.0x)

```python
from image_anonymizer import ImageAnonymizer

config = {"custom_terms": {"schools": ["National Taiwan University"]}}
img_anon = ImageAnonymizer(config=config, use_ner=False)
output_path, summary = img_anon.anonymize_image("input.jpg", output_dir="output/")
```

## Batch Processing

```python
from batch import run_batch

result = run_batch(
    input_dir="./sensitive_docs",
    output_dir=None,  # Default: sensitive_docs_anonymized/
    config=config,
    reversible=False,
    use_ner=False,
)
print(result.summary())
```

## Configuration

`config.json` structure (schema v1):

```json
{
    "version": 1,
    "custom_terms": {
        "schools": ["National Taiwan University", "National Tsing Hua University"],
        "people": ["John Doe", "Jane Smith"]
    },
    "file_types": [".txt", ".md", ".docx", ".pdf", ".jpg", ".png"],
    "logo_templates": ["ntu_logo.png"],
    "substring_match": true
}
```

Configs can be exported as `.anonymizer-config.zip` (including logo templates) for one-click import by colleagues.

## Building the Windows Installer

Push a version tag to trigger the GitHub Actions build:

```bash
git tag v2.0.0
git push origin v2.0.0
```

Two editions are built:
- **Full** — Includes NER (PyTorch + ckip-transformers), ~2-3GB
- **Lite** — Custom terms + regex only, ~150-250MB

## Testing

```bash
.venv/bin/python -m pytest -v
```

196 tests currently passing.

## Project Structure

```
anonymizer.py          # Core text anonymization engine
image_anonymizer.py    # Image anonymization pipeline (OCR + Face + Logo)
hook_router.py         # Claude Code PreToolUse hook router
restore.py             # PostToolUse restore hook
batch.py               # Batch processing
config_manager.py      # Config export/import
mapping_manager.py     # Token mapping manager
updater.py             # Auto-update checker
models.py              # Span data model + overlap resolver
detectors/             # Detection engines (custom, regex, NER)
parsers/               # File parsers (text, docx, xlsx, pptx, pdf, image)
gui/                   # Flask Web UI
  web_app.py           # Flask backend + API
  templates/           # HTML templates
  static/              # CSS, JS, fonts
tests/                 # Tests (196 tests)
anonymizer.spec        # PyInstaller build spec
installer.iss          # Inno Setup installer script
.github/workflows/     # CI/CD
```

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — Free to use, modify, and share. No commercial use.

**Attribution format:**
```
Based on Data Anonymizer by Cheng-I Wu
https://github.com/Imbad0202/data-anonymizer
```
