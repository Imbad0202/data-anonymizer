import pdfplumber


class PdfParser:
    EXTENSIONS = {'.pdf'}
    OUTPUT_EXTENSION = ".txt"

    def parse(self, file_path: str, max_pages: int = 50) -> str:
        try:
            pdf = pdfplumber.open(file_path)
        except Exception:
            return ""
        parts = []
        with pdf:
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    break
                text = page.extract_text()
                if text:
                    parts.append(text)
        return '\n'.join(parts)

    def anonymize_to_path(self, file_path: str, output_path: str, anonymizer):
        text = self.parse(file_path, max_pages=anonymizer.max_file_pages)
        anonymized, spans = anonymizer._anonymize_text_with_spans(text)
        if not spans:
            return False, []
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(anonymized)
        return True, spans
