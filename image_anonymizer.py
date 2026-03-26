"""
image_anonymizer.py — 3-stage image anonymization pipeline.

Pipeline:
  INPUT IMAGE
       │
       ├──▶ [Stage 1: OCR Text PII]
       │     pytesseract.image_to_data(lang='chi_tra+eng')
       │     → text + bboxes → existing detectors → ImageRegion list
       │     Failure: Tesseract not found → log warning, return []
       │
       ├──▶ [Stage 2: Face Detection]
       │     OpenCV DNN (res10_300x300_ssd_iter_140000.caffemodel)
       │     → face bounding boxes
       │     Failure: model missing → log warning, return []
       │
       ├──▶ [Stage 3: Logo Detection]
       │     OpenCV matchTemplate (multi-scale 0.5x–2.0x)
       │     → logo bounding boxes
       │     Failure: no templates → skip silently
       │
       └──▶ [Merge & Redact]
             merge_regions(IoU > 0.3)
             Reversible: Gaussian blur (kernel=51)
             Irreversible: solid black fill
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageFilter

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore

from detectors import build_detectors, collect_spans
from PIL import ImageDraw

logger = logging.getLogger(__name__)

# Face detection model files (expected in models/ directory next to this file)
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
_FACE_PROTO = os.path.join(_MODELS_DIR, "deploy.prototxt")
_FACE_MODEL = os.path.join(_MODELS_DIR, "res10_300x300_ssd_iter_140000.caffemodel")

# Face detection confidence threshold
_FACE_CONFIDENCE = 0.5

# Logo matching threshold (normalized cross-correlation)
_LOGO_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ImageRegion:
    """A rectangular region detected in an image."""
    x: int
    y: int
    w: int
    h: int
    region_type: str  # "text_pii", "face", "logo"
    label: str        # e.g. "SCHOOL", "PERSON", "" for face/logo

    @property
    def area(self) -> int:
        return self.w * self.h

    def iou(self, other: "ImageRegion") -> float:
        """Intersection over Union between two regions."""
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Region merging
# ---------------------------------------------------------------------------

def merge_regions(regions: List[ImageRegion], iou_threshold: float = 0.3) -> List[ImageRegion]:
    """Merge overlapping regions (IoU > threshold) into bounding boxes."""
    if not regions:
        return []

    merged: List[ImageRegion] = []
    used = [False] * len(regions)

    for i, r in enumerate(regions):
        if used[i]:
            continue

        # Start a group with this region
        group = [r]
        used[i] = True

        # Find all overlapping regions
        for j in range(i + 1, len(regions)):
            if used[j]:
                continue
            if any(g.iou(regions[j]) > iou_threshold for g in group):
                group.append(regions[j])
                used[j] = True

        # Compute bounding box of the group
        min_x = min(g.x for g in group)
        min_y = min(g.y for g in group)
        max_x = max(g.x + g.w for g in group)
        max_y = max(g.y + g.h for g in group)

        merged.append(ImageRegion(
            x=min_x, y=min_y,
            w=max_x - min_x, h=max_y - min_y,
            region_type=group[0].region_type,
            label=group[0].label,
        ))

    return merged


# ---------------------------------------------------------------------------
# Image Anonymizer
# ---------------------------------------------------------------------------

class ImageAnonymizer:
    """3-stage image anonymization: OCR text PII + face detection + logo matching."""

    def __init__(self, config: dict, use_ner: bool = False):
        self.config = config

        # Text detectors (shared with Anonymizer)
        self.custom_detector, self.regex_detector, self.ner_detector = build_detectors(config, use_ner)

        # Logo templates — cache loaded images to avoid re-reading per image
        self._logo_templates: List[str] = config.get("logo_templates", [])
        self._template_cache: Dict[str, np.ndarray] = {}
        for path in self._logo_templates:
            if os.path.isfile(path):
                tmpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    self._template_cache[path] = tmpl

        # Face detection model (lazy load)
        self._face_net = self._load_face_model()

    def _load_face_model(self):
        """Load OpenCV DNN face detection model. Returns None if unavailable."""
        if not os.path.isfile(_FACE_PROTO) or not os.path.isfile(_FACE_MODEL):
            logger.warning("Face detection model not found at %s — skipping face detection.", _MODELS_DIR)
            return None
        try:
            return cv2.dnn.readNetFromCaffe(_FACE_PROTO, _FACE_MODEL)
        except Exception as e:
            logger.warning("Failed to load face detection model: %s", e)
            return None

    # ------------------------------------------------------------------
    # Stage 1: OCR text PII
    # ------------------------------------------------------------------

    def _stage_ocr(self, img: Image.Image) -> List[ImageRegion]:
        """Run Tesseract OCR and detect PII in extracted text."""
        if pytesseract is None:
            logger.warning("pytesseract not installed — skipping OCR stage.")
            return []

        try:
            data = pytesseract.image_to_data(
                img, lang="chi_tra+eng", output_type=None,
            )
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s — skipping OCR stage.", e)
            return []

        # When output_type is None, pytesseract returns a dict
        if not isinstance(data, dict):
            return []

        texts = data.get("text", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])
        confs = data.get("conf", [])

        # Reconstruct full text and map character offsets to bounding boxes
        # Strategy: concatenate OCR words, track (offset, bbox) for each word
        word_entries = []  # (start_offset, end_offset, left, top, width, height)
        full_text_parts = []
        offset = 0

        for i in range(len(texts)):
            word = str(texts[i]).strip()
            if not word:
                continue
            try:
                conf = int(confs[i]) if confs[i] != "-1" else -1
            except (ValueError, TypeError):
                conf = -1
            if conf == -1:
                continue

            start = offset
            end = offset + len(word)
            word_entries.append((start, end, int(lefts[i]), int(tops[i]), int(widths[i]), int(heights[i])))
            full_text_parts.append(word)
            offset = end

        full_text = "".join(full_text_parts)
        if not full_text:
            return []

        # Run detectors on the concatenated text (shared pipeline)
        spans = collect_spans(full_text, self.custom_detector, self.regex_detector, self.ner_detector)

        if not spans:
            return []

        # Map each span back to image bounding boxes
        regions: List[ImageRegion] = []
        for span in spans:
            # Find all words that overlap with this span
            min_x, min_y = float("inf"), float("inf")
            max_x, max_y = 0, 0
            found = False

            for ws, we, wl, wt, ww, wh in word_entries:
                # Word overlaps with span?
                if ws < span.end and we > span.start:
                    min_x = min(min_x, wl)
                    min_y = min(min_y, wt)
                    max_x = max(max_x, wl + ww)
                    max_y = max(max_y, wt + wh)
                    found = True

            if found:
                regions.append(ImageRegion(
                    x=int(min_x), y=int(min_y),
                    w=int(max_x - min_x), h=int(max_y - min_y),
                    region_type="text_pii",
                    label=span.category,
                ))

        return regions

    # ------------------------------------------------------------------
    # Stage 2: Face detection
    # ------------------------------------------------------------------

    def _stage_face(self, img: Image.Image) -> List[ImageRegion]:
        """Detect faces using OpenCV DNN."""
        if self._face_net is None:
            return []

        try:
            np_img = np.array(img)
            h, w = np_img.shape[:2]

            blob = cv2.dnn.blobFromImage(
                cv2.resize(np_img, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0),
            )
            self._face_net.setInput(blob)
            detections = self._face_net.forward()

            regions: List[ImageRegion] = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence < _FACE_CONFIDENCE:
                    continue

                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")

                # Clamp to image boundaries
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                if x2 > x1 and y2 > y1:
                    regions.append(ImageRegion(
                        x=x1, y=y1,
                        w=x2 - x1, h=y2 - y1,
                        region_type="face",
                        label="FACE",
                    ))

            return regions

        except Exception as e:
            logger.warning("Face detection failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Stage 3: Logo template matching
    # ------------------------------------------------------------------

    def _stage_logo(self, img: Image.Image) -> List[ImageRegion]:
        """Detect logos using multi-scale template matching."""
        if not self._logo_templates:
            return []

        np_img = np.array(img)
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

        regions: List[ImageRegion] = []

        for template_path in self._logo_templates:
            template = self._template_cache.get(template_path)
            if template is None:
                logger.warning("Logo template not loaded: %s — skipping.", template_path)
                continue

            try:
                th, tw = template.shape[:2]
                best_val = -1.0
                best_loc = (0, 0)
                best_scale = 1.0

                # Multi-scale search: 0.5x to 2.0x in 0.1 steps
                for scale_10 in range(5, 21):
                    scale = scale_10 / 10.0
                    new_w = int(tw * scale)
                    new_h = int(th * scale)

                    if new_w < 10 or new_h < 10:
                        continue
                    if new_w > gray.shape[1] or new_h > gray.shape[0]:
                        continue

                    resized = cv2.resize(template, (new_w, new_h))
                    result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(result)

                    if max_val > best_val:
                        best_val = max_val
                        best_loc = max_loc
                        best_scale = scale

                    # Early exit: good enough match found
                    if best_val >= _LOGO_THRESHOLD:
                        break

                if best_val >= _LOGO_THRESHOLD:
                    match_w = int(tw * best_scale)
                    match_h = int(th * best_scale)
                    regions.append(ImageRegion(
                        x=best_loc[0], y=best_loc[1],
                        w=match_w, h=match_h,
                        region_type="logo",
                        label="LOGO",
                    ))

            except Exception as e:
                logger.warning("Logo matching failed for %s: %s", template_path, e)
                continue

        return regions

    # ------------------------------------------------------------------
    # Redaction
    # ------------------------------------------------------------------

    def _redact(self, img: Image.Image, regions: List[ImageRegion], reversible: bool = True) -> Image.Image:
        """Apply redaction to detected regions.

        Reversible: Gaussian blur (kernel=51).
        Irreversible: solid black fill.
        """
        result = img.copy()

        if not reversible:
            draw = ImageDraw.Draw(result)

        for r in regions:
            if reversible:
                box = (r.x, r.y, r.x + r.w, r.y + r.h)
                cropped = result.crop(box)
                blurred = cropped.filter(ImageFilter.GaussianBlur(radius=25))
                result.paste(blurred, box)
            else:
                draw.rectangle([r.x, r.y, r.x + r.w, r.y + r.h], fill=(0, 0, 0))

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def anonymize_image(
        self,
        image_path: str,
        output_dir: str,
        reversible: bool = True,
    ) -> Tuple[Optional[str], str]:
        """
        Run the full 3-stage pipeline on an image.

        Returns
        -------
        (output_path_or_None, summary_string)
        """
        from parsers.image_parser import ImageParser
        parser = ImageParser()
        img = parser.parse(image_path)
        if img is None:
            return None, f"無法讀取圖片：{os.path.basename(image_path)}"

        # Run all three stages
        regions: List[ImageRegion] = []
        regions.extend(self._stage_ocr(img))
        regions.extend(self._stage_face(img))
        regions.extend(self._stage_logo(img))

        if not regions:
            return None, f"圖片《{os.path.basename(image_path)}》未發現敏感資訊。"

        # Merge overlapping regions
        merged = merge_regions(regions, iou_threshold=0.3)

        # Redact
        result_img = self._redact(img, merged, reversible=reversible)

        # Save output
        os.makedirs(output_dir, exist_ok=True)
        basename = os.path.basename(image_path)
        name, ext = os.path.splitext(basename)
        output_path = os.path.join(output_dir, f"{name}_anonymized{ext}")

        # JPEG: save with quality=95
        save_kwargs = {}
        if ext.lower() in (".jpg", ".jpeg"):
            save_kwargs["quality"] = 95

        result_img.save(output_path, **save_kwargs)

        # Build summary
        type_counts: Dict[str, int] = {}
        for r in merged:
            key = r.label or r.region_type
            type_counts[key] = type_counts.get(key, 0) + 1

        parts = [f"{k} {v} 個" for k, v in sorted(type_counts.items())]
        summary = f"已脫敏圖片《{basename}》：{'、'.join(parts)}"

        return output_path, summary
