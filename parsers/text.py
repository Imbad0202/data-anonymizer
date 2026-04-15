class TextParser:
    EXTENSIONS = {'.md', '.csv', '.json', '.txt', '.html', '.xml'}

    def parse(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception:
            return ""

    def anonymize_to_path(self, file_path: str, output_path: str, anonymizer):
        text = self.parse(file_path)
        anonymized, spans = anonymizer._anonymize_text_with_spans(text)
        if not spans:
            return False, []
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(anonymized)
        return True, spans
