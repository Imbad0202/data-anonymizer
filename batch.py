"""
batch.py — Batch processing wrapper for folder-level anonymization.

Recursively scans a folder, processes text + image files through
the anonymizer/image_anonymizer pipelines, outputs to {folder}_anonymized/
preserving directory structure.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from anonymizer import Anonymizer, get_parser
from config_manager import DEFAULT_FILE_TYPES
from image_anonymizer import ImageAnonymizer
from parsers.image_parser import ImageParser

logger = logging.getLogger(__name__)

# Image extensions handled by ImageAnonymizer
IMAGE_EXTENSIONS = set(ImageParser.EXTENSIONS)


@dataclass
class BatchResult:
    """Summary of a batch processing run."""
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    pii_found_files: int = 0
    file_results: List[Dict[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"共 {self.total_files} 個檔案",
            f"已處理 {self.processed_files} 個",
            f"發現個資 {self.pii_found_files} 個",
        ]
        if self.skipped_files:
            parts.append(f"跳過 {self.skipped_files} 個")
        if self.error_files:
            parts.append(f"錯誤 {self.error_files} 個")
        return "批次處理完成：" + "、".join(parts)


def _collect_files(input_dir: str, file_types: List[str]) -> List[str]:
    """Recursively collect files matching file_types from input_dir."""
    files = []
    file_types_lower = {ft.lower() for ft in file_types}

    for root, _dirs, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext in file_types_lower:
                files.append(os.path.join(root, fname))
    return files


def run_batch(
    input_dir: str,
    output_dir: Optional[str],
    config: dict,
    reversible: bool = True,
    use_ner: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> BatchResult:
    """Process all matching files in input_dir.

    Parameters
    ----------
    input_dir : str
        Root folder to scan recursively.
    output_dir : str or None
        Output folder. If None, defaults to {input_dir}_anonymized.
    config : dict
        Anonymizer config dict.
    reversible : bool
        True for pseudonymization, False for anonymization.
    use_ner : bool
        Whether to use NER detection.
    progress_callback : callable or None
        Called with (current_index, total_count, current_file) for progress updates.

    Returns
    -------
    BatchResult
    """
    if not os.path.isdir(input_dir):
        raise ValueError(f"輸入資料夾不存在：{input_dir}")

    if output_dir is None:
        output_dir = input_dir.rstrip(os.sep) + "_anonymized"

    file_types = config.get("file_types") or DEFAULT_FILE_TYPES

    files = _collect_files(input_dir, file_types)
    result = BatchResult(total_files=len(files))

    if not files:
        return result

    # Initialize engines
    session_id = f"batch_{os.path.basename(input_dir)}"
    text_anon = Anonymizer(config=config, session_id=session_id,
                           use_ner=use_ner, reversible=reversible)
    img_anon = ImageAnonymizer(config=config, use_ner=use_ner)

    for idx, file_path in enumerate(files):
        rel_path = os.path.relpath(file_path, input_dir)
        out_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if progress_callback:
            progress_callback(idx, len(files), rel_path)

        ext = os.path.splitext(file_path)[1].lower()
        file_result = {"file": rel_path, "status": "ok", "detail": ""}

        try:
            if ext in IMAGE_EXTENSIONS:
                # Image pipeline
                anon_path, summary = img_anon.anonymize_image(
                    file_path,
                    output_dir=os.path.dirname(out_path),
                    reversible=reversible,
                )
                if anon_path:
                    # Move to correct output path if different
                    if os.path.abspath(anon_path) != os.path.abspath(out_path):
                        shutil.move(anon_path, out_path)
                    result.pii_found_files += 1
                    file_result["detail"] = summary
                else:
                    # No PII found — copy original
                    shutil.copy2(file_path, out_path)
                    file_result["detail"] = summary
                result.processed_files += 1

            else:
                # Text pipeline
                parser = get_parser(file_path)
                if parser is None:
                    # Unsupported — copy as-is
                    shutil.copy2(file_path, out_path)
                    result.skipped_files += 1
                    file_result["status"] = "skipped"
                    file_result["detail"] = "不支援的檔案格式"
                    result.file_results.append(file_result)
                    continue

                text = parser.parse(file_path)

                anon_text, summary = text_anon.anonymize_text(text)

                if anon_text != text:
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(anon_text)
                    result.pii_found_files += 1
                else:
                    shutil.copy2(file_path, out_path)

                file_result["detail"] = summary
                result.processed_files += 1

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)
            result.error_files += 1
            file_result["status"] = "error"
            file_result["detail"] = str(e)
            # Copy original on error so output is complete
            try:
                shutil.copy2(file_path, out_path)
            except Exception:
                pass

        result.file_results.append(file_result)

    return result
