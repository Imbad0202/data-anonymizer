import json
import os
from dataclasses import replace
from typing import List, Tuple

from models import Span


class LearnedTermsManager:
    DEFAULT_PATH = os.path.expanduser("~/.claude/anonymizer/learned_terms.json")

    def __init__(self, path: str = None):
        self.path = path if path is not None else self.DEFAULT_PATH
        self._sensitive: set = set()
        self._safe: set = set()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._sensitive = set(data.get("confirmed_sensitive", []))
            self._safe = set(data.get("confirmed_safe", []))
        else:
            self._sensitive = set()
            self._safe = set()

    def add_sensitive(self, term: str):
        self._sensitive.add(term)
        self._safe.discard(term)

    def add_safe(self, term: str):
        self._safe.add(term)
        self._sensitive.discard(term)

    def is_confirmed_sensitive(self, term: str) -> bool:
        return term in self._sensitive

    def is_confirmed_safe(self, term: str) -> bool:
        return term in self._safe

    def save(self):
        data = {
            "confirmed_sensitive": sorted(self._sensitive),
            "confirmed_safe": sorted(self._safe),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def filter_spans(
        self, spans: List[Span], confidence_threshold: float = 0.8
    ) -> Tuple[List[Span], List[Span]]:
        kept: List[Span] = []
        uncertain: List[Span] = []

        for span in spans:
            if span.confidence >= confidence_threshold:
                # High confidence → always keep as-is
                kept.append(span)
            elif self.is_confirmed_sensitive(span.text):
                # Low confidence but learned sensitive → promote and keep
                kept.append(replace(span, confidence=1.0))
            elif self.is_confirmed_safe(span.text):
                # Low confidence and learned safe → drop
                pass
            else:
                # Low confidence and unknown → uncertain
                uncertain.append(span)

        return kept, uncertain
