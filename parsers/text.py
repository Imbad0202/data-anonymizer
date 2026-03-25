class TextParser:
    EXTENSIONS = {'.md', '.csv', '.json', '.txt', '.html', '.xml'}

    def parse(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception:
            return ""
