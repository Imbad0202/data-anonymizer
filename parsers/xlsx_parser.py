from openpyxl import load_workbook


class XlsxParser:
    EXTENSIONS = {'.xlsx'}

    def parse(self, file_path: str) -> str:
        try:
            wb = load_workbook(file_path, data_only=True)
        except Exception:
            return ""
        parts = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None:
                        parts.append(str(cell))
        return '\n'.join(parts)
