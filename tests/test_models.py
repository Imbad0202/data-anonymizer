import pytest
from models import Span, resolve_spans

class TestSpan:
    def test_span_creation(self):
        s = Span(start=0, end=5, text="hello", category="PERSON", token="__ANON:PERSON_001__", confidence=0.95, source="ner")
        assert s.start == 0
        assert s.end == 5
        assert s.length == 5

    def test_span_overlap_detection(self):
        a = Span(0, 10, "0123456789", "SCHOOL", "__ANON:SCHOOL_001__", 1.0, "custom")
        b = Span(5, 15, "56789abcde", "ORG", "__ANON:ORG_001__", 0.9, "ner")
        assert a.overlaps(b)

    def test_span_no_overlap(self):
        a = Span(0, 5, "01234", "PERSON", "__ANON:PERSON_001__", 1.0, "custom")
        b = Span(5, 10, "56789", "PERSON", "__ANON:PERSON_002__", 1.0, "custom")
        assert not a.overlaps(b)

class TestResolveSpans:
    def test_no_overlap_keeps_all(self):
        spans = [
            Span(0, 3, "ABC", "SCHOOL", "__ANON:SCHOOL_001__", 1.0, "custom"),
            Span(10, 15, "DEFGH", "PERSON", "__ANON:PERSON_001__", 0.9, "ner"),
        ]
        resolved = resolve_spans(spans)
        assert len(resolved) == 2

    def test_overlap_longest_wins(self):
        short = Span(0, 5, "01234", "ORG", "__ANON:ORG_001__", 0.9, "ner")
        long = Span(0, 10, "0123456789", "SCHOOL", "__ANON:SCHOOL_001__", 1.0, "custom")
        resolved = resolve_spans([short, long])
        assert len(resolved) == 1
        assert resolved[0].category == "SCHOOL"

    def test_same_length_priority_custom_over_ner(self):
        custom = Span(0, 5, "01234", "SCHOOL", "__ANON:SCHOOL_001__", 1.0, "custom")
        ner = Span(0, 5, "01234", "ORG", "__ANON:ORG_001__", 0.95, "ner")
        resolved = resolve_spans([ner, custom])
        assert len(resolved) == 1
        assert resolved[0].source == "custom"

    def test_same_length_priority_ner_over_regex(self):
        ner = Span(0, 5, "01234", "PERSON", "__ANON:PERSON_001__", 0.9, "ner")
        regex = Span(0, 5, "01234", "PHONE", "__ANON:PHONE_001__", 1.0, "regex")
        resolved = resolve_spans([regex, ner])
        assert len(resolved) == 1
        assert resolved[0].source == "ner"
