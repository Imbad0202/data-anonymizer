import re
from typing import List

from models import Span

# Each entry: (compiled_pattern, category)
_PATTERNS = [
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), "EMAIL"),
    (re.compile(r'09\d{2}[-]?\d{3}[-]?\d{3}'), "PHONE"),
    (re.compile(r'0(?!9)[2-9][-]?\d{4}[-]?\d{4}'), "PHONE"),
    (re.compile(r'[A-Z][12]\d{8}'), "ID"),
    (re.compile(r'\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}'), "FINANCE"),
    (re.compile(r'https?://[^\s<>"{}|\\^\`\[\]]+'), "URL"),
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), "URL"),
]


class RegexDetector:
    def detect(self, text: str) -> List[Span]:
        spans: List[Span] = []
        for pattern, category in _PATTERNS:
            for m in pattern.finditer(text):
                spans.append(Span(
                    start=m.start(),
                    end=m.end(),
                    text=m.group(),
                    category=category,
                    token="",
                    confidence=1.0,
                    source="regex",
                ))
        spans.sort(key=lambda s: s.start)
        return spans
