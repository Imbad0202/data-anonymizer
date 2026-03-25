import re
from typing import List, Dict

from models import Span

CATEGORY_MAP = {
    "schools": "SCHOOL",
    "colleges": "COLLEGE",
    "departments": "DEPT",
    "institutes": "INST",
    "documents": "DOC",
    "locations": "LOCATION",
}


class CustomDetector:
    def __init__(self, custom_terms: Dict[str, List[str]], substring_match: bool = True):
        self.substring_match = substring_match
        # Build list of (term, category) sorted by length desc so longer matches found first
        self._entries: List[tuple] = []
        for group, terms in custom_terms.items():
            category = CATEGORY_MAP.get(group, group.upper())
            for term in terms:
                self._entries.append((term, category))
        self._entries.sort(key=lambda x: len(x[0]), reverse=True)

    def detect(self, text: str) -> List[Span]:
        spans: List[Span] = []
        for term, category in self._entries:
            if len(term) <= 2:
                # Short terms require word boundary match
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(term), re.IGNORECASE)

            for m in pattern.finditer(text):
                span = Span(
                    start=m.start(),
                    end=m.end(),
                    text=m.group(),
                    category=category,
                    token="",
                    confidence=1.0,
                    source="custom",
                )
                spans.append(span)

        # Sort by start position
        spans.sort(key=lambda s: s.start)
        return spans
