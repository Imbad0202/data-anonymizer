import os
from typing import List

from models import Span

# Map ckip NER tags to our category names
_TAG_MAP = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "ORG": "ORG",
    "FAC": "LOCATION",
}

# Lazy-load singleton
_ner_chunker = None


def _get_chunker():
    global _ner_chunker
    if _ner_chunker is None:
        from ckip_transformers.nlp import CkipNerChunker
        local_model = os.environ.get('CKIP_MODEL_DIR')
        if local_model and os.path.isdir(local_model):
            _ner_chunker = CkipNerChunker(model=local_model)
        else:
            _ner_chunker = CkipNerChunker(model="bert-base")
    return _ner_chunker


class NERDetector:
    def detect(self, text: str) -> List[Span]:
        if not text:
            return []

        chunker = _get_chunker()
        ner_results = chunker([text], batch_size=256)

        spans: List[Span] = []
        used_positions: set = set()

        for entity in ner_results[0]:
            ner_tag = entity.ner
            if ner_tag not in _TAG_MAP:
                continue

            word = entity.word
            category = _TAG_MAP[ner_tag]

            # Find first unused occurrence to handle duplicate entities correctly
            search_start = 0
            while search_start < len(text):
                pos = text.find(word, search_start)
                if pos == -1:
                    break
                if pos not in used_positions:
                    used_positions.add(pos)
                    spans.append(Span(
                        start=pos,
                        end=pos + len(word),
                        text=word,
                        category=category,
                        token="",
                        confidence=0.85,
                        source="ner",
                    ))
                    break
                search_start = pos + 1

        spans.sort(key=lambda s: s.start)
        return spans
