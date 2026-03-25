from pptx import Presentation


class PptxParser:
    EXTENSIONS = {'.pptx'}

    def parse(self, file_path: str) -> str:
        try:
            prs = Presentation(file_path)
        except Exception:
            return ""
        parts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        parts.append(para.text)
                if shape.has_table:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            parts.append(cell.text)
        return '\n'.join(parts)
