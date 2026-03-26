"""
test_image_parser.py — Tests for image file parser.
"""

import os
import tempfile

import pytest
from PIL import Image

from parsers.image_parser import ImageParser


class TestImageParser:
    def setup_method(self):
        self.parser = ImageParser()

    def test_extensions(self):
        assert ".jpg" in ImageParser.EXTENSIONS
        assert ".jpeg" in ImageParser.EXTENSIONS
        assert ".png" in ImageParser.EXTENSIONS
        assert ".bmp" in ImageParser.EXTENSIONS
        assert ".tiff" in ImageParser.EXTENSIONS

    def test_parse_png(self, tmp_path):
        img = Image.new("RGB", (100, 50), color="white")
        path = tmp_path / "test.png"
        img.save(str(path))

        result = self.parser.parse(str(path))
        assert isinstance(result, Image.Image)
        assert result.size == (100, 50)

    def test_parse_jpg(self, tmp_path):
        img = Image.new("RGB", (200, 100), color="red")
        path = tmp_path / "test.jpg"
        img.save(str(path))

        result = self.parser.parse(str(path))
        assert isinstance(result, Image.Image)
        assert result.size == (200, 100)

    def test_parse_bmp(self, tmp_path):
        img = Image.new("RGB", (80, 60), color="blue")
        path = tmp_path / "test.bmp"
        img.save(str(path))

        result = self.parser.parse(str(path))
        assert isinstance(result, Image.Image)

    def test_parse_nonexistent_returns_none(self):
        result = self.parser.parse("/tmp/nonexistent_image.png")
        assert result is None

    def test_parse_corrupt_file_returns_none(self, tmp_path):
        path = tmp_path / "corrupt.png"
        path.write_bytes(b"this is not an image")

        result = self.parser.parse(str(path))
        assert result is None
