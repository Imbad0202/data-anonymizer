from dataclasses import dataclass
from typing import List

SOURCE_PRIORITY = {"custom": 0, "ner": 1, "regex": 2}

@dataclass
class Span:
    start: int
    end: int
    text: str
    category: str
    token: str
    confidence: float
    source: str

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

def resolve_spans(spans: List[Span]) -> List[Span]:
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda s: (-s.length, SOURCE_PRIORITY.get(s.source, 99)))
    accepted: List[Span] = []
    for candidate in sorted_spans:
        if not any(candidate.overlaps(a) for a in accepted):
            accepted.append(candidate)
    return sorted(accepted, key=lambda s: s.start)
