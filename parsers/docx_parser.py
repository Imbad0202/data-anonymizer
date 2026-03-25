from docx import Document


class DocxParser:
    EXTENSIONS = {'.docx'}

    def parse(self, file_path: str) -> str:
        try:
            doc = Document(file_path)
        except Exception:
            return ""
        parts = []
        for para in doc.paragraphs:
            parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
        return '\n'.join(parts)
