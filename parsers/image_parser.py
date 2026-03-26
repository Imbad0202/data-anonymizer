"""
image_parser.py — Load image files for the image anonymization pipeline.

Returns a PIL Image object, or None if the file cannot be loaded.
"""

from PIL import Image
from typing import Optional


class ImageParser:
    EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]

    def parse(self, file_path: str) -> Optional[Image.Image]:
        """Load an image file and return a PIL Image, or None on failure."""
        try:
            img = Image.open(file_path)
            img.load()  # Force full load to catch truncated files
            return img
        except Exception:
            return None
