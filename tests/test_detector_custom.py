import pytest
from detectors.custom import CustomDetector

class TestCustomDetector:
    def setup_method(self):
        self.config = {
            "schools": ["國立OO大學", "OO大"],
            "colleges": ["XX學院"],
            "departments": ["資訊工程學系", "資工系"],
            "locations": ["某某路123號"],
        }
        self.detector = CustomDetector(self.config, substring_match=True)

    def test_exact_match(self):
        spans = self.detector.detect("國立OO大學是一所好學校")
        assert len(spans) >= 1
        assert any(s.text == "國立OO大學" for s in spans)
        assert all(s.confidence == 1.0 for s in spans)
        assert all(s.source == "custom" for s in spans)

    def test_substring_containment(self):
        spans = self.detector.detect("我在OO大學資訊工程學系讀書")
        texts = {s.text for s in spans}
        assert "資訊工程學系" in texts

    def test_case_insensitive_english(self):
        config = {"schools": ["OOU", "National OO University"]}
        det = CustomDetector(config, substring_match=True)
        spans = det.detect("I study at oou")
        assert len(spans) == 1

    def test_short_term_exact_boundary(self):
        config = {"departments": ["AI"]}
        det = CustomDetector(config, substring_match=True)
        spans = det.detect("The AI department")
        assert len(spans) == 1
        spans = det.detect("FAIR research")
        assert len(spans) == 0

    def test_no_match(self):
        spans = self.detector.detect("今天天氣很好")
        assert len(spans) == 0

    def test_multiple_matches(self):
        spans = self.detector.detect("國立OO大學XX學院位於某某路123號")
        categories = {s.category for s in spans}
        assert "SCHOOL" in categories
        assert "COLLEGE" in categories
        assert "LOCATION" in categories
