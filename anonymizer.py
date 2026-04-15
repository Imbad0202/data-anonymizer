import os
from typing import Dict, List, Optional, Tuple

from detectors import build_detectors, collect_spans
from mapping_manager import MappingManager, TMP_ANONYMIZER_DIR
from models import Span


def get_parser(file_path: str):
    """Return the appropriate parser instance for the given file extension, or None."""
    from parsers.docx_parser import DocxParser
    from parsers.pdf_parser import PdfParser
    from parsers.pptx_parser import PptxParser
    from parsers.text import TextParser
    from parsers.xlsx_parser import XlsxParser

    ext = os.path.splitext(file_path)[1].lower()
    for parser_cls in (TextParser, DocxParser, XlsxParser, PptxParser, PdfParser):
        if ext in parser_cls.EXTENSIONS:
            return parser_cls()
    return None


class Anonymizer:
    def __init__(self, config: dict, session_id: str, use_ner: bool = True, reversible: bool = True):
        self.config = config
        self.session_id = session_id
        self.use_ner = use_ner
        self.reversible = reversible
        self.persist_mapping: bool = config.get("persist_mapping", True)
        self.max_file_pages: int = config.get("max_file_pages", 50)

        self.mapping = MappingManager(session_id=session_id, reversible=reversible)
        self.custom_detector, self.regex_detector, self.ner_detector = build_detectors(config, use_ner)

    def _collect_spans(self, text: str) -> List[Span]:
        """Run all enabled detectors on text and return resolved spans."""
        return collect_spans(text, self.custom_detector, self.regex_detector, self.ner_detector)

    def _apply_spans(self, text: str, spans: List[Span]) -> str:
        """Replace spans right-to-left so that earlier offsets are preserved."""
        result = text
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            token = self.mapping.get_or_create_token(span.text, span.category)
            result = result[: span.start] + token + result[span.end :]
        return result

    def anonymize_value(self, text: str) -> Tuple[str, List[Span]]:
        """Anonymize one text fragment and return the collected spans."""
        spans = self._collect_spans(text)
        if not spans:
            return text, []
        return self._apply_spans(text, spans), spans

    def _anonymize_text_with_spans(self, text: str) -> Tuple[str, List[Span]]:
        """Backward-compatible alias used by parser implementations and tests."""
        return self.anonymize_value(text)

    def _build_summary(self, spans: List[Span], file_path: Optional[str] = None) -> str:
        if not spans:
            prefix = f"檔案《{os.path.basename(file_path)}》：" if file_path else ""
            return f"{prefix}未發現個資，文件未修改。"

        category_counts: Dict[str, int] = {}
        for span in spans:
            category_counts[span.category] = category_counts.get(span.category, 0) + 1

        parts = [f"{cat} {cnt} 個" for cat, cnt in sorted(category_counts.items())]
        detail = "、".join(parts)

        if file_path:
            return f"已脫敏檔案《{os.path.basename(file_path)}》：{detail}"
        return f"已脫敏：{detail}"

    def anonymize_text(self, text: str) -> Tuple[str, str]:
        """Anonymize plain text and return (text, summary)."""
        anonymized, spans = self.anonymize_value(text)
        if not spans:
            return text, self._build_summary([])

        summary = self._build_summary(spans)
        if self.persist_mapping:
            self.mapping.save()

        return anonymized, summary

    def anonymize_file_to_text_temp(self, file_path: str) -> Tuple[Optional[str], str]:
        """Parse a file and write anonymized extracted text to a temp `.txt` file."""
        parser = get_parser(file_path)
        if parser is None:
            return None, f"不支援的檔案格式：{os.path.splitext(file_path)[1]}"

        text = parser.parse(file_path)
        anonymized, spans = self.anonymize_value(text)
        if not spans:
            return None, self._build_summary([], file_path=file_path)

        anon_path = self.mapping.register_file_path(file_path, extension=".txt")
        parent = os.path.dirname(anon_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(anon_path, "w", encoding="utf-8") as f:
            f.write(anonymized)

        if self.persist_mapping:
            self.mapping.save()

        return anon_path, self._build_summary(spans, file_path=file_path)

    def anonymize_file_to_path(self, file_path: str, output_path: str) -> Tuple[Optional[str], str]:
        """Write an anonymized file to an explicit output path when PII is found."""
        parser = get_parser(file_path)
        if parser is None:
            return None, f"不支援的檔案格式：{os.path.splitext(file_path)[1]}"

        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        changed, spans = parser.anonymize_to_path(file_path, output_path, self)
        if not changed:
            return None, self._build_summary([], file_path=file_path)

        if self.persist_mapping:
            self.mapping.save()

        return output_path, self._build_summary(spans, file_path=file_path)

    def anonymize_file(self, file_path: str) -> Tuple[Optional[str], str]:
        """Anonymize a file and write the result to a temp path using a safe output format."""
        parser = get_parser(file_path)
        if parser is None:
            return None, f"不支援的檔案格式：{os.path.splitext(file_path)[1]}"

        output_ext = getattr(parser, "OUTPUT_EXTENSION", os.path.splitext(file_path)[1].lower() or ".txt")
        anon_path = self.mapping.register_file_path(file_path, extension=output_ext)
        return self.anonymize_file_to_path(file_path, anon_path)


def cleanup(max_age_hours: int = 24) -> list:
    """Remove anonymized temp files and session mappings older than max_age_hours."""
    import glob
    import time

    cutoff = time.time() - (max_age_hours * 3600)
    removed = []
    for f in glob.glob(os.path.join(TMP_ANONYMIZER_DIR, "*")):
        try:
            if os.path.getmtime(f) < cutoff:
                os.unlink(f)
                removed.append(f)
        except OSError:
            pass
    return removed


if __name__ == "__main__":
    import sys

    if "--cleanup" in sys.argv:
        removed = cleanup()
        for f in removed:
            print(f"Cleaned: {f}")
        print(f"Total: {len(removed)} files removed")
    else:
        print("Usage: python3 anonymizer.py --cleanup")
