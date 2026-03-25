import pdfplumber


class PdfParser:
    EXTENSIONS = {'.pdf'}

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
