import logging
import os
import re
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
                _ner_chunker = CkipNerChunker(model_name=local_model)
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
    # Texts longer than this are split into lines for better recall on
    # tabular content (e.g. xlsx cells joined by newlines).
    _CHUNK_THRESHOLD = 512

    def detect(self, text: str) -> List[Span]:
        if not text:
            return []

        chunker = _get_chunker()
        if chunker is None:
            _warn_backend_unavailable()
            return []

        if len(text) > self._CHUNK_THRESHOLD and "\n" in text:
            return self._detect_chunked(text, chunker)
        return self._detect_single(text, chunker)

    def _detect_single(self, text: str, chunker) -> List[Span]:
        try:
            ner_results = chunker([text], batch_size=256, show_progress=False)
        except Exception as exc:
            _set_backend_error(exc)
            _warn_backend_unavailable()
            return []

        return self._extract_spans(text, ner_results[0])

    def _detect_chunked(self, text: str, chunker) -> List[Span]:
        """Split text on newlines and batch-detect for better NER recall."""
        lines = text.split("\n")
        offsets = []
        non_empty_lines = []
        pos = 0
        for line in lines:
            if line.strip():
                offsets.append(pos)
                non_empty_lines.append(line)
            pos += len(line) + 1  # +1 for the \n

        if not non_empty_lines:
            return []

        try:
            ner_results = chunker(non_empty_lines, batch_size=256, show_progress=False)
        except Exception as exc:
            _set_backend_error(exc)
            _warn_backend_unavailable()
            return []

        all_spans: List[Span] = []
        for line_offset, line_text, entities in zip(offsets, non_empty_lines, ner_results):
            for span in self._extract_spans(line_text, entities):
                all_spans.append(Span(
                    start=span.start + line_offset,
                    end=span.end + line_offset,
                    text=span.text,
                    category=span.category,
                    token="",
                    confidence=span.confidence,
                    source="ner",
                ))

        all_spans.sort(key=lambda s: s.start)
        return all_spans

    # Patterns that CKIP misclassifies as PERSON (e.g. time ranges "03-04")
    _FALSE_PERSON = re.compile(r"^\s*\d{1,2}[-–]\d{1,2}\s*$")

    @classmethod
    def _extract_spans(cls, text: str, entities) -> List[Span]:
        spans: List[Span] = []
        used_positions: set = set()

        for entity in entities:
            ner_tag = entity.ner
            if ner_tag not in _TAG_MAP:
                continue

            word = entity.word
            category = _TAG_MAP[ner_tag]

            if category == "PERSON" and cls._FALSE_PERSON.match(word):
                continue

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

        return spans
