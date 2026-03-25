import pytest
from detectors.ner import NERDetector


class TestNERDetector:
    @pytest.fixture(scope="class")
    def detector(self):
        return NERDetector()

    def test_detects_person_name(self, detector):
        spans = detector.detect("張三是一位教授")
        person_spans = [s for s in spans if s.category == "PERSON"]
        assert len(person_spans) >= 1
        assert any("張三" in s.text for s in person_spans)

    def test_detects_location(self, detector):
        spans = detector.detect("他住在台北市信義區")
        location_spans = [s for s in spans if s.category == "LOCATION"]
        assert len(location_spans) >= 1

    def test_confidence_score(self, detector):
        spans = detector.detect("王小明在台北工作")
        assert all(0.0 <= s.confidence <= 1.0 for s in spans)
        assert all(s.source == "ner" for s in spans)

    def test_empty_text(self, detector):
        spans = detector.detect("")
        assert spans == []
