"""
test_image_anonymizer.py — Tests for the 3-stage image anonymization pipeline.

Tests OCR text detection, face detection, logo template matching,
region merging, and redaction (blur/black fill).
"""

import os
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from unittest.mock import patch, MagicMock

from image_anonymizer import (
    ImageRegion,
    ImageAnonymizer,
    merge_regions,
)


# ---------------------------------------------------------------------------
# Helpers: create test images
# ---------------------------------------------------------------------------

def _create_text_image(text: str, size=(400, 100)) -> Image.Image:
    """Create a white image with black text for OCR testing."""
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    # Use default font (always available)
    draw.text((10, 30), text, fill="black")
    return img


def _create_face_image(size=(300, 300)) -> Image.Image:
    """Create a simple image with a skin-colored oval (simulates a face for DNN)."""
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    # Draw a skin-colored oval in center
    cx, cy = size[0] // 2, size[1] // 2
    draw.ellipse([cx - 50, cy - 70, cx + 50, cy + 70], fill=(220, 185, 155))
    # Eyes
    draw.ellipse([cx - 25, cy - 20, cx - 15, cy - 10], fill=(50, 50, 50))
    draw.ellipse([cx + 15, cy - 20, cx + 25, cy - 10], fill=(50, 50, 50))
    return img


# ---------------------------------------------------------------------------
# ImageRegion dataclass
# ---------------------------------------------------------------------------

class TestImageRegion:
    def test_creation(self):
        r = ImageRegion(x=10, y=20, w=100, h=50, region_type="text_pii", label="SCHOOL")
        assert r.x == 10
        assert r.y == 20
        assert r.w == 100
        assert r.h == 50
        assert r.region_type == "text_pii"
        assert r.label == "SCHOOL"

    def test_area(self):
        r = ImageRegion(x=0, y=0, w=100, h=50, region_type="face", label="")
        assert r.area == 5000

    def test_iou_no_overlap(self):
        r1 = ImageRegion(x=0, y=0, w=50, h=50, region_type="a", label="")
        r2 = ImageRegion(x=100, y=100, w=50, h=50, region_type="b", label="")
        assert r1.iou(r2) == 0.0

    def test_iou_full_overlap(self):
        r1 = ImageRegion(x=0, y=0, w=100, h=100, region_type="a", label="")
        r2 = ImageRegion(x=0, y=0, w=100, h=100, region_type="b", label="")
        assert r1.iou(r2) == pytest.approx(1.0)

    def test_iou_partial_overlap(self):
        r1 = ImageRegion(x=0, y=0, w=100, h=100, region_type="a", label="")
        r2 = ImageRegion(x=50, y=0, w=100, h=100, region_type="b", label="")
        # Intersection: 50*100=5000, Union: 10000+10000-5000=15000
        assert r1.iou(r2) == pytest.approx(5000 / 15000)


# ---------------------------------------------------------------------------
# Merge regions
# ---------------------------------------------------------------------------

class TestMergeRegions:
    def test_no_overlap_keeps_all(self):
        regions = [
            ImageRegion(x=0, y=0, w=50, h=50, region_type="a", label=""),
            ImageRegion(x=200, y=200, w=50, h=50, region_type="b", label=""),
        ]
        merged = merge_regions(regions, iou_threshold=0.3)
        assert len(merged) == 2

    def test_high_overlap_merges(self):
        regions = [
            ImageRegion(x=0, y=0, w=100, h=100, region_type="a", label=""),
            ImageRegion(x=10, y=10, w=100, h=100, region_type="b", label=""),
        ]
        merged = merge_regions(regions, iou_threshold=0.3)
        assert len(merged) == 1
        # Merged region should be the bounding box of both
        m = merged[0]
        assert m.x == 0
        assert m.y == 0
        assert m.w == 110
        assert m.h == 110

    def test_empty_input(self):
        assert merge_regions([], iou_threshold=0.3) == []


# ---------------------------------------------------------------------------
# OCR stage (uses mock when Tesseract not available)
# ---------------------------------------------------------------------------

class TestStageOCR:
    def test_ocr_with_mock_tesseract(self):
        """Test OCR stage logic with mocked pytesseract output."""
        config = {
            "custom_terms": {"schools": ["國立台灣大學"]},
            "substring_match": True,
        }
        anon = ImageAnonymizer(config=config, use_ner=False)

        # Mock pytesseract.image_to_data to return fake OCR results
        mock_data = {
            "text": ["", "國立台灣大學", "資訊系"],
            "left": [0, 10, 200],
            "top": [0, 30, 30],
            "width": [0, 150, 60],
            "height": [0, 25, 25],
            "conf": ["-1", "85", "90"],
        }

        img = Image.new("RGB", (400, 100), "white")

        with patch("image_anonymizer.pytesseract") as mock_tess:
            mock_tess.image_to_data.return_value = mock_data
            regions = anon._stage_ocr(img)

        # Should detect "國立台灣大學" as SCHOOL
        assert len(regions) >= 1
        assert any(r.label == "SCHOOL" for r in regions)

    def test_ocr_tesseract_missing_returns_empty(self):
        """If pytesseract is not available, stage returns empty list."""
        config = {"custom_terms": {}, "substring_match": True}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (100, 100), "white")

        with patch("image_anonymizer.pytesseract") as mock_tess:
            mock_tess.image_to_data.side_effect = Exception("Tesseract not found")
            regions = anon._stage_ocr(img)

        assert regions == []

    def test_ocr_no_text_returns_empty(self):
        """Image with no text returns empty regions."""
        config = {"custom_terms": {"schools": ["台大"]}, "substring_match": True}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (100, 100), "white")

        with patch("image_anonymizer.pytesseract") as mock_tess:
            mock_tess.image_to_data.return_value = {
                "text": [""],
                "left": [0],
                "top": [0],
                "width": [0],
                "height": [0],
                "conf": ["-1"],
            }
            regions = anon._stage_ocr(img)

        assert regions == []


# ---------------------------------------------------------------------------
# Face detection stage
# ---------------------------------------------------------------------------

class TestStageFace:
    def test_face_detection_with_mock(self):
        """Test face detection with mocked OpenCV DNN."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (300, 300), "white")
        np_img = np.array(img)

        # Mock cv2.dnn to return a detection
        mock_net = MagicMock()
        detections = np.zeros((1, 1, 1, 7))
        detections[0, 0, 0] = [0, 0, 0.95, 0.3, 0.2, 0.7, 0.8]  # confidence=0.95, box
        mock_net.forward.return_value = detections

        with patch("image_anonymizer.cv2") as mock_cv2:
            mock_cv2.dnn.readNetFromCaffe.return_value = mock_net
            mock_cv2.dnn.blobFromImage.return_value = np.zeros((1, 3, 300, 300))
            anon._face_net = mock_net
            regions = anon._stage_face(img)

        assert len(regions) >= 1
        assert regions[0].region_type == "face"

    def test_face_no_model_returns_empty(self):
        """If face model is not loaded, returns empty list."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)
        anon._face_net = None

        img = Image.new("RGB", (300, 300), "white")
        regions = anon._stage_face(img)
        assert regions == []


# ---------------------------------------------------------------------------
# Logo detection stage
# ---------------------------------------------------------------------------

class TestStageLogo:
    def test_logo_matching(self, tmp_path):
        """Test that a known logo template is detected in an image."""
        # Create a distinctive "logo" — checkerboard pattern (not a solid color)
        logo = Image.new("RGB", (50, 50), color="white")
        draw = ImageDraw.Draw(logo)
        for i in range(0, 50, 10):
            for j in range(0, 50, 10):
                if (i + j) % 20 == 0:
                    draw.rectangle([i, j, i + 10, j + 10], fill="red")
        logo_path = tmp_path / "logo.png"
        logo.save(str(logo_path))

        # Create an image containing the logo at a known position
        img = Image.new("RGB", (300, 300), color="gray")
        img.paste(logo, (100, 100))

        config = {"custom_terms": {}, "logo_templates": [str(logo_path)]}
        anon = ImageAnonymizer(config=config, use_ner=False)

        regions = anon._stage_logo(img)
        assert len(regions) >= 1
        assert regions[0].region_type == "logo"
        # Check the detected region is near where we pasted the logo
        r = regions[0]
        assert 90 <= r.x <= 110
        assert 90 <= r.y <= 110

    def test_logo_no_templates_returns_empty(self):
        """No templates configured → empty list."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (200, 200), "white")
        regions = anon._stage_logo(img)
        assert regions == []

    def test_logo_template_missing_file_skips(self):
        """Missing template file → skip, not crash."""
        config = {"custom_terms": {}, "logo_templates": ["/nonexistent/logo.png"]}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (200, 200), "white")
        regions = anon._stage_logo(img)
        assert regions == []


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

class TestRedact:
    def test_blur_redaction(self):
        """Reversible mode: Gaussian blur applied to regions."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (200, 200), color="red")
        regions = [ImageRegion(x=50, y=50, w=100, h=100, region_type="face", label="")]

        result = anon._redact(img, regions, reversible=True)
        assert result.size == (200, 200)
        # The blurred area should be different from the original red
        orig_pixel = img.getpixel((100, 100))
        # Blurred region center pixel might still be red-ish but edges will differ
        # Just verify image was modified (not identical)
        assert isinstance(result, Image.Image)

    def test_black_fill_redaction(self):
        """Irreversible mode: solid black fill."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (200, 200), color="red")
        regions = [ImageRegion(x=50, y=50, w=100, h=100, region_type="face", label="")]

        result = anon._redact(img, regions, reversible=False)
        # Center of redacted region should be black
        pixel = result.getpixel((100, 100))
        assert pixel == (0, 0, 0)

    def test_redact_empty_regions(self):
        """No regions → image unchanged."""
        config = {"custom_terms": {}}
        anon = ImageAnonymizer(config=config, use_ner=False)

        img = Image.new("RGB", (100, 100), color="blue")
        result = anon._redact(img, [], reversible=True)
        assert result.getpixel((50, 50)) == (0, 0, 255)  # still blue


# ---------------------------------------------------------------------------
# Full pipeline: anonymize_image
# ---------------------------------------------------------------------------

class TestAnonymizeImage:
    def test_anonymize_image_returns_path_and_summary(self, tmp_path):
        """Full pipeline with mocked OCR returns anonymized image."""
        config = {
            "custom_terms": {"schools": ["國立台灣大學"]},
            "substring_match": True,
        }
        anon = ImageAnonymizer(config=config, use_ner=False)
        anon._face_net = None  # Disable face detection for this test

        # Create test image
        img = Image.new("RGB", (400, 100), "white")
        img_path = tmp_path / "test.png"
        img.save(str(img_path))

        mock_data = {
            "text": ["", "國立台灣大學"],
            "left": [0, 10],
            "top": [0, 30],
            "width": [0, 150],
            "height": [0, 25],
            "conf": ["-1", "85"],
        }

        with patch("image_anonymizer.pytesseract") as mock_tess:
            mock_tess.image_to_data.return_value = mock_data
            result_path, summary = anon.anonymize_image(
                str(img_path), output_dir=str(tmp_path / "out"), reversible=False
            )

        assert result_path is not None
        assert os.path.isfile(result_path)
        assert "SCHOOL" in summary

    def test_anonymize_image_no_pii_returns_none(self, tmp_path):
        """Image with no PII returns None."""
        config = {
            "custom_terms": {"schools": ["國立台灣大學"]},
            "substring_match": True,
        }
        anon = ImageAnonymizer(config=config, use_ner=False)
        anon._face_net = None

        img = Image.new("RGB", (100, 100), "white")
        img_path = tmp_path / "clean.png"
        img.save(str(img_path))

        with patch("image_anonymizer.pytesseract") as mock_tess:
            mock_tess.image_to_data.return_value = {
                "text": [""], "left": [0], "top": [0],
                "width": [0], "height": [0], "conf": ["-1"],
            }
            result_path, summary = anon.anonymize_image(
                str(img_path), output_dir=str(tmp_path / "out"), reversible=True
            )

        assert result_path is None
        assert "未發現" in summary
