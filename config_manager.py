"""
config_manager.py — Export/import anonymizer configuration as .zip bundles.

Config schema v1:
{
    "version": 1,
    "custom_terms": {"schools": ["校名"], ...},
    "file_types": [".txt", ".md", ...],
    "logo_templates": ["ntu_logo.png"],
    "substring_match": true
}

Export: config.json + logo_templates/ directory → .anonymizer-config.zip
Import: validate schema version, extract to app data dir.
"""

import json
import logging
import os
import shutil
import zipfile
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

DEFAULT_FILE_TYPES = [
    ".txt", ".md", ".docx", ".xlsx", ".pptx", ".pdf",
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff",
]

# Required top-level keys and their types
_SCHEMA_KEYS = {
    "version": int,
    "custom_terms": dict,
    "file_types": list,
    "logo_templates": list,
    "substring_match": bool,
}

# Optional keys that setup.py may add (not required for validation)
_OPTIONAL_KEYS = {
    "auto_detect": bool,
    "sensitivity": str,
    "scan_paths": list,
    "persist_mapping": bool,
    "max_file_pages": int,
    "hook_timeout_seconds": int,
}


def validate_config(config: dict) -> Tuple[bool, str]:
    """Validate config dict against schema v1.

    Returns (is_valid, error_message). error_message is empty if valid.
    """
    if not isinstance(config, dict):
        return False, "設定檔格式錯誤：不是有效的 JSON 物件"

    version = config.get("version")
    if version is None:
        return False, "設定檔缺少 version 欄位"
    if version != CURRENT_SCHEMA_VERSION:
        return False, f"不支援的設定檔版本：{version}（目前支援版本 {CURRENT_SCHEMA_VERSION}）"

    for key, expected_type in _SCHEMA_KEYS.items():
        if key not in config:
            return False, f"設定檔缺少必要欄位：{key}"
        if not isinstance(config[key], expected_type):
            return False, f"欄位 {key} 類型錯誤：預期 {expected_type.__name__}，實際 {type(config[key]).__name__}"

    # Validate optional keys if present
    for key, expected_type in _OPTIONAL_KEYS.items():
        if key in config and not isinstance(config[key], expected_type):
            return False, f"欄位 {key} 類型錯誤：預期 {expected_type.__name__}，實際 {type(config[key]).__name__}"

    # Validate custom_terms values are lists of strings
    for category, terms in config["custom_terms"].items():
        if not isinstance(terms, list):
            return False, f"custom_terms[{category}] 必須是字串列表"
        for term in terms:
            if not isinstance(term, str):
                return False, f"custom_terms[{category}] 包含非字串項目：{term}"

    # Validate file_types are strings starting with "."
    for ft in config["file_types"]:
        if not isinstance(ft, str) or not ft.startswith("."):
            return False, f"file_types 格式錯誤：{ft}（應為 .ext 格式）"

    # Validate logo_templates are strings
    for lt in config["logo_templates"]:
        if not isinstance(lt, str):
            return False, f"logo_templates 包含非字串項目：{lt}"

    return True, ""


def create_default_config() -> dict:
    """Return a minimal default config."""
    return {
        "version": CURRENT_SCHEMA_VERSION,
        "custom_terms": {},
        "file_types": list(DEFAULT_FILE_TYPES),
        "logo_templates": [],
        "substring_match": True,
    }


def export_config(config: dict, logo_dir: str, output_path: str) -> str:
    """Export config + logo templates to a .zip file.

    Parameters
    ----------
    config : dict
        The config dict to export.
    logo_dir : str
        Directory containing logo template images.
    output_path : str
        Path for the output .zip file.

    Returns
    -------
    str
        The absolute path of the created zip file.
    """
    if not output_path.endswith(".zip"):
        output_path += ".zip"

    exported_config = dict(config)
    exported_logos = [os.path.basename(path) for path in config.get("logo_templates", [])]
    exported_config["logo_templates"] = exported_logos

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write config.json
        config_json = json.dumps(exported_config, ensure_ascii=False, indent=2)
        zf.writestr("config.json", config_json)

        # Bundle logo templates
        if os.path.isdir(logo_dir):
            for raw_path, fname in zip(config.get("logo_templates", []), exported_logos):
                fpath = raw_path if os.path.isabs(raw_path) else os.path.join(logo_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, f"logo_templates/{fname}")

    return os.path.abspath(output_path)


def import_config(zip_path: str, target_dir: str) -> Tuple[dict, str]:
    """Import config from a .zip file.

    Parameters
    ----------
    zip_path : str
        Path to the .anonymizer-config.zip file.
    target_dir : str
        Directory to extract logo templates into (target_dir/logo_templates/).

    Returns
    -------
    (config_dict, summary_message)

    Raises
    ------
    ValueError
        If the zip is invalid or config fails validation.
    """
    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except FileNotFoundError:
        raise ValueError(f"檔案不存在：{zip_path}")
    except zipfile.BadZipFile:
        raise ValueError(f"不是有效的 zip 檔案：{zip_path}")

    with zf:
        names = zf.namelist()

        if "config.json" not in names:
            raise ValueError("zip 檔案中缺少 config.json")

        config_bytes = zf.read("config.json")
        try:
            config = json.loads(config_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"config.json 解析失敗：{e}")

        is_valid, error = validate_config(config)
        if not is_valid:
            raise ValueError(error)

        logo_dir = os.path.join(target_dir, "logo_templates")
        os.makedirs(logo_dir, exist_ok=True)

        extracted_logos = []
        for name in names:
            if name.startswith("logo_templates/") and not name.endswith("/"):
                # Prevent path traversal
                basename = os.path.basename(name)
                if not basename:
                    continue
                dest = os.path.join(logo_dir, basename)
                with zf.open(name) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_logos.append(basename)

    # Update logo_templates paths to point to extracted files
    config["logo_templates"] = extracted_logos

    # Build summary
    terms_count = sum(len(v) for v in config["custom_terms"].values())
    summary_parts = [f"自訂詞彙 {terms_count} 個"]
    if extracted_logos:
        summary_parts.append(f"logo 模板 {len(extracted_logos)} 個")
    summary = f"已匯入設定：{'、'.join(summary_parts)}"

    return config, summary


def save_config(config: dict, config_path: str) -> None:
    """Save config dict to a JSON file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config(config_path: str) -> dict:
    """Load config from JSON file. Returns default config if file doesn't exist."""
    if not os.path.isfile(config_path):
        return create_default_config()
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_logo_template_paths(config: dict, logo_dir: str) -> dict:
    """Return a shallow config copy with logo template entries resolved to full paths."""
    resolved = dict(config)
    resolved["logo_templates"] = [
        path if os.path.isabs(path) else os.path.join(logo_dir, path)
        for path in config.get("logo_templates", [])
    ]
    return resolved
