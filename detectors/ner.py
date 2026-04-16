import logging
import os
from typing import List, Optional

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
_ner_backend_error: Optional[str] = None
_ner_warning_emitted = False

logger = logging.getLogger(__name__)


def _set_backend_error(exc: Exception) -> None:
    """Record the latest backend error and clear the cached chunker."""
    global _ner_chunker, _ner_backend_error
    _ner_chunker = None
    _ner_backend_error = f"{type(exc).__name__}: {exc}"


def get_ner_backend_error() -> Optional[str]:
    """Return the most recent backend initialization or inference error."""
    return _ner_backend_error


def _warn_backend_unavailable() -> None:
    """Emit a single warning when the NER backend is unavailable."""
    global _ner_warning_emitted
    if _ner_warning_emitted or not _ner_backend_error:
        return
    logger.warning("NER backend unavailable: %s", _ner_backend_error)
    _ner_warning_emitted = True


def _get_chunker():
    global _ner_chunker
    if _ner_chunker is None:
        try:
            from ckip_transformers.nlp import CkipNerChunker

            local_model = os.environ.get("CKIP_MODEL_DIR")
            if local_model and os.path.isdir(local_model):
                _ner_chunker = CkipNerChunker(model=local_model)
            else:
                _ner_chunker = CkipNerChunker(model="bert-base")
        except Exception as exc:
            _set_backend_error(exc)
    return _ner_chunker


def ner_backend_available(probe: bool = False) -> bool:
    """Return True when the CKIP backend is usable in the current environment."""
    chunker = _get_chunker()
    if chunker is None:
        return False
    if not probe:
        return True

    try:
        chunker(["王小明"], batch_size=1, show_progress=False)
    except Exception as exc:
        _set_backend_error(exc)
        return False
    return True


class NERDetector:
    def detect(self, text: str) -> List[Span]:
        if not text:
            return []

        chunker = _get_chunker()
        if chunker is None:
            _warn_backend_unavailable()
            return []

        try:
            ner_results = chunker([text], batch_size=256, show_progress=False)
        except Exception as exc:
            _set_backend_error(exc)
            _warn_backend_unavailable()
            return []

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
