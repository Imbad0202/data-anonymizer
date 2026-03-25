import pytest
from detectors.regex_detector import RegexDetector

class TestRegexDetector:
    def setup_method(self):
        self.detector = RegexDetector()

    def test_email(self):
        spans = self.detector.detect("聯絡 test@example.com 或 foo@bar.edu.tw")
        assert len(spans) == 2
        assert all(s.category == "EMAIL" for s in spans)

    def test_taiwan_phone(self):
        spans = self.detector.detect("電話 0912-345-678 或 0912345678")
        assert len(spans) == 2
        assert all(s.category == "PHONE" for s in spans)

    def test_taiwan_landline(self):
        spans = self.detector.detect("辦公室 02-2345-6789")
        assert len(spans) == 1
        assert spans[0].category == "PHONE"

    def test_roc_id(self):
        spans = self.detector.detect("身分證 A123456789")
        assert len(spans) == 1
        assert spans[0].category == "ID"

    def test_credit_card(self):
        spans = self.detector.detect("卡號 4111-1111-1111-1111")
        assert len(spans) == 1
        assert spans[0].category == "FINANCE"

    def test_url(self):
        spans = self.detector.detect("網址 https://school.edu.tw/~professor/grades")
        assert any(s.category == "URL" for s in spans)

    def test_ip_address(self):
        spans = self.detector.detect("伺服器 192.168.1.100")
        assert len(spans) == 1
        assert spans[0].category == "URL"

    def test_no_match(self):
        spans = self.detector.detect("今天天氣很好，出去走走")
        assert len(spans) == 0
