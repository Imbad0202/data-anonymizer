"""
Shared detector utilities.
"""

from typing import Dict, List, Optional, Tuple

from models import Span, resolve_spans
from detectors.custom import CustomDetector
from detectors.regex_detector import RegexDetector



def build_detectors(config: dict, use_ner: bool) -> Tuple[CustomDetector, RegexDetector, Optional[object]]:
    """Build the standard detector set from config. Shared by Anonymizer and ImageAnonymizer."""
    custom_terms: Dict[str, List[str]] = config.get("custom_terms", {})
    substring_match: bool = config.get("substring_match", True)
    custom_detector = CustomDetector(custom_terms=custom_terms, substring_match=substring_match)
    regex_detector = RegexDetector()

    ner_detector = None
    if use_ner:
        from detectors.ner import NERDetector
        ner_detector = NERDetector()

    return custom_detector, regex_detector, ner_detector


def collect_spans(
    text: str,
    custom_detector: CustomDetector,
    regex_detector: RegexDetector,
    ner_detector: Optional[object] = None,
) -> List[Span]:
    """Run all enabled detectors and return resolved spans. Shared by Anonymizer and ImageAnonymizer."""
    all_spans: List[Span] = []
    all_spans.extend(custom_detector.detect(text))
    all_spans.extend(regex_detector.detect(text))
    if ner_detector is not None:
        all_spans.extend(ner_detector.detect(text))
    return resolve_spans(all_spans)
