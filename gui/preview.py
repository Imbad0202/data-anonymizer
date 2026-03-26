"""
gui/preview.py — Before/After preview panel for the anonymizer GUI.

Text preview: diff-highlighted view showing replaced spans in color.
Image preview: side-by-side with original and redacted versions (800px max width).
"""

import os
import tkinter as tk
from tkinter import ttk
from typing import Optional

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


MAX_PREVIEW_WIDTH = 800
MAX_PREVIEW_HEIGHT = 600


class PreviewPanel(ttk.Frame):
    """Embeddable Before/After preview panel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._photo_refs = []  # prevent GC of PhotoImage objects

        # Title
        self._title_var = tk.StringVar(value="預覽")
        ttk.Label(self, textvariable=self._title_var,
                  font=("", 12, "bold")).pack(anchor="w", padx=5, pady=(5, 0))

        # Notebook for switching between text and image preview
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Text preview tab
        self._text_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._text_frame, text="文字預覽")
        self._build_text_tab()

        # Image preview tab
        self._image_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._image_frame, text="圖片預覽")
        self._build_image_tab()

    def _build_text_tab(self):
        # Before / After side-by-side
        paned = ttk.PanedWindow(self._text_frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Before
        before_frame = ttk.LabelFrame(paned, text="原始內容")
        self._text_before = tk.Text(before_frame, wrap="word", state="disabled",
                                    height=15, width=40)
        scroll_b = ttk.Scrollbar(before_frame, command=self._text_before.yview)
        self._text_before.configure(yscrollcommand=scroll_b.set)
        self._text_before.pack(side="left", fill="both", expand=True)
        scroll_b.pack(side="right", fill="y")
        paned.add(before_frame, weight=1)

        # After
        after_frame = ttk.LabelFrame(paned, text="脫敏結果")
        self._text_after = tk.Text(after_frame, wrap="word", state="disabled",
                                   height=15, width=40)
        scroll_a = ttk.Scrollbar(after_frame, command=self._text_after.yview)
        self._text_after.configure(yscrollcommand=scroll_a.set)
        self._text_after.pack(side="left", fill="both", expand=True)
        scroll_a.pack(side="right", fill="y")
        paned.add(after_frame, weight=1)

        # Configure highlight tag
        self._text_after.tag_configure("pii", background="#ffcccc", foreground="#cc0000")

    def _build_image_tab(self):
        paned = ttk.PanedWindow(self._image_frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        before_frame = ttk.LabelFrame(paned, text="原始圖片")
        self._img_before_label = ttk.Label(before_frame)
        self._img_before_label.pack(fill="both", expand=True, padx=2, pady=2)
        paned.add(before_frame, weight=1)

        after_frame = ttk.LabelFrame(paned, text="脫敏結果")
        self._img_after_label = ttk.Label(after_frame)
        self._img_after_label.pack(fill="both", expand=True, padx=2, pady=2)
        paned.add(after_frame, weight=1)

    def show_text_preview(self, original: str, anonymized: str, filename: str = ""):
        """Show text before/after with diff highlighting."""
        self._title_var.set(f"預覽：{filename}" if filename else "文字預覽")
        self._notebook.select(self._text_frame)
        self._photo_refs.clear()

        self._text_before.configure(state="normal")
        self._text_before.delete("1.0", "end")
        self._text_before.insert("1.0", original)
        self._text_before.configure(state="disabled")

        # After — with highlighting for changed parts
        self._text_after.configure(state="normal")
        self._text_after.delete("1.0", "end")
        self._text_after.insert("1.0", anonymized)

        # Highlight tokens and labels in the anonymized text
        import re
        # Match __ANON:XXX_NNN__ tokens or [CATEGORY] labels
        patterns = [
            r'__ANON:[A-Z]+_\d+__',
            r'\[[A-Z_]+\]',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, anonymized):
                start_idx = f"1.0+{m.start()}c"
                end_idx = f"1.0+{m.end()}c"
                self._text_after.tag_add("pii", start_idx, end_idx)

        self._text_after.configure(state="disabled")

    def show_image_preview(self, original_path: str, anonymized_path: Optional[str],
                           filename: str = ""):
        """Show image before/after side-by-side."""
        if Image is None or ImageTk is None:
            return

        self._title_var.set(f"預覽：{filename}" if filename else "圖片預覽")
        self._notebook.select(self._image_frame)
        self._photo_refs.clear()

        # Load and resize original
        try:
            orig_img = Image.open(original_path)
            orig_thumb = self._resize_thumbnail(orig_img)
            orig_photo = ImageTk.PhotoImage(orig_thumb)
            self._photo_refs.append(orig_photo)
            self._img_before_label.configure(image=orig_photo)
        except Exception:
            self._img_before_label.configure(image="", text="無法載入原始圖片")

        # Load and resize anonymized
        if anonymized_path and os.path.isfile(anonymized_path):
            try:
                anon_img = Image.open(anonymized_path)
                anon_thumb = self._resize_thumbnail(anon_img)
                anon_photo = ImageTk.PhotoImage(anon_thumb)
                self._photo_refs.append(anon_photo)
                self._img_after_label.configure(image=anon_photo)
            except Exception:
                self._img_after_label.configure(image="", text="無法載入脫敏圖片")
        else:
            self._img_after_label.configure(image="", text="未發現敏感資訊")

    def _resize_thumbnail(self, img: "Image.Image") -> "Image.Image":
        """Resize image to fit within MAX dimensions, maintaining aspect ratio."""
        # Each side gets half the width
        max_w = MAX_PREVIEW_WIDTH // 2
        max_h = MAX_PREVIEW_HEIGHT
        w, h = img.size
        ratio = min(max_w / w, max_h / h, 1.0)
        if ratio < 1.0:
            new_size = (int(w * ratio), int(h * ratio))
            return img.resize(new_size, Image.LANCZOS)
        return img.copy()

    def clear(self):
        """Clear all preview content."""
        self._title_var.set("預覽")

        self._text_before.configure(state="normal")
        self._text_before.delete("1.0", "end")
        self._text_before.configure(state="disabled")

        self._text_after.configure(state="normal")
        self._text_after.delete("1.0", "end")
        self._text_after.configure(state="disabled")

        self._photo_refs.clear()
        self._img_before_label.configure(image="", text="")
        self._img_after_label.configure(image="", text="")
