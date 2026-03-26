"""
gui/app.py — Main tkinter GUI for the Data Anonymizer.

Features:
- File picker (click) + optional TkDND drag-and-drop
- Mode selector: reversible (pseudonymization) / irreversible (anonymization)
- Single file + batch folder processing
- Before/After preview panel
- Config import/export
- Passive auto-update banner
- Progress bar
"""

import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Add parent dir to path for imports when running as script
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from anonymizer import Anonymizer, get_parser
from batch import run_batch, _collect_files
from config_manager import (
    DEFAULT_FILE_TYPES,
    create_default_config,
    export_config,
    import_config,
    load_config,
    save_config,
    validate_config,
)
from gui.preview import PreviewPanel
from image_anonymizer import ImageAnonymizer
from parsers.image_parser import ImageParser
from updater import check_for_update

logger = logging.getLogger(__name__)

# Where config lives alongside the executable (or in dev: project root)
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOGO_DIR = os.path.join(APP_DIR, "logo_templates")

IMAGE_EXTENSIONS = set(ImageParser.EXTENSIONS)

# Mode constants
MODE_REVERSIBLE = "reversible"
MODE_IRREVERSIBLE = "irreversible"

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700


class AnonymizerApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("資料脫敏工具 Data Anonymizer")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(700, 500)

        # Load config
        self._config = load_config(CONFIG_PATH)
        ok, err = validate_config(self._config)
        if not ok:
            self._config = create_default_config()

        # State
        self._processing = False
        # Cached engine instances (invalidated when config/mode/ner changes)
        self._cached_engines = None
        self._cached_engines_key = None

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_status_bar()

        # Auto-update check (background thread, non-blocking)
        self._check_update_async()

        # First-launch config detection
        self._check_first_launch_config()

    # ------------------------------------------------------------------
    # Engine caching
    # ------------------------------------------------------------------

    def _get_engines(self):
        """Return (text_anon, img_anon) tuple, cached across calls."""
        reversible = self._mode_var.get() == MODE_REVERSIBLE
        use_ner = self._ner_var.get()
        key = (id(self._config), reversible, use_ner)

        if self._cached_engines_key != key:
            text_anon = Anonymizer(config=self._config, session_id="gui_session",
                                   use_ner=use_ner, reversible=reversible)
            img_anon = ImageAnonymizer(config=self._config, use_ner=use_ner)
            self._cached_engines = (text_anon, img_anon)
            self._cached_engines_key = key

        return self._cached_engines

    def _invalidate_engines(self):
        self._cached_engines = None
        self._cached_engines_key = None

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="開啟檔案...", command=self._on_open_file,
                              accelerator="Ctrl+O")
        file_menu.add_command(label="開啟資料夾...", command=self._on_open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="匯入設定...", command=self._on_import_config)
        file_menu.add_command(label="匯出設定...", command=self._on_export_config)
        file_menu.add_separator()
        file_menu.add_command(label="結束", command=self.quit)
        menubar.add_cascade(label="檔案", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="關於", command=self._on_about)
        menubar.add_cascade(label="說明", menu=help_menu)

        self.config(menu=menubar)
        self.bind_all("<Control-o>", lambda e: self._on_open_file())

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=5, pady=(5, 0))

        ttk.Label(toolbar, text="模式：").pack(side="left")
        self._mode_var = tk.StringVar(value=MODE_REVERSIBLE)
        mode_frame = ttk.Frame(toolbar)
        mode_frame.pack(side="left", padx=(0, 15))
        ttk.Radiobutton(mode_frame, text="假名化（可還原）",
                         variable=self._mode_var, value=MODE_REVERSIBLE).pack(side="left")
        ttk.Radiobutton(mode_frame, text="匿名化（不可逆）",
                         variable=self._mode_var, value=MODE_IRREVERSIBLE).pack(side="left")

        self._ner_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="NER 偵測", variable=self._ner_var).pack(side="left", padx=(0, 15))

        ttk.Button(toolbar, text="開啟檔案", command=self._on_open_file).pack(side="left", padx=2)
        ttk.Button(toolbar, text="批次處理", command=self._on_open_folder).pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Main area: drop zone + preview
    # ------------------------------------------------------------------

    def _build_main_area(self):
        main = ttk.PanedWindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=5, pady=5)

        top_frame = ttk.LabelFrame(main, text="檔案")
        self._file_list = tk.Listbox(top_frame, height=6, selectmode="extended")
        scroll = ttk.Scrollbar(top_frame, command=self._file_list.yview)
        self._file_list.configure(yscrollcommand=scroll.set)
        self._file_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._drop_hint = ttk.Label(
            top_frame,
            text="點擊「開啟檔案」或「批次處理」選擇要脫敏的檔案",
            foreground="gray",
        )
        self._drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        self._file_list.bind("<<ListboxSelect>>", self._on_file_select)
        main.add(top_frame, weight=1)

        action_frame = ttk.Frame(main)
        self._process_btn = ttk.Button(action_frame, text="開始脫敏",
                                        command=self._on_process)
        self._process_btn.pack(side="left", padx=5)
        self._progress = ttk.Progressbar(action_frame, mode="determinate", length=300)
        self._progress.pack(side="left", fill="x", expand=True, padx=5)
        self._progress_label = ttk.Label(action_frame, text="")
        self._progress_label.pack(side="left", padx=5)
        main.add(action_frame, weight=0)

        self._preview = PreviewPanel(main)
        main.add(self._preview, weight=2)

        self._setup_dnd()

    def _setup_dnd(self):
        """Try to enable TkDND drag-and-drop. Falls back to click-only."""
        try:
            self.tk.eval('package require tkdnd')
            self.tk.eval(f'tkdnd::drop_target register {self._file_list} *')
            self._file_list.bind('<<Drop>>', self._on_drop)
        except tk.TclError:
            pass

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        self._add_files(files)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self):
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", side="bottom", padx=5, pady=(0, 5))

        self._status_var = tk.StringVar(value="就緒")
        ttk.Label(status_frame, textvariable=self._status_var).pack(side="left")

        self._update_frame = ttk.Frame(status_frame)
        self._update_label = ttk.Label(self._update_frame, text="", foreground="blue",
                                        cursor="hand2")
        self._update_label.pack(side="left")
        self._update_label.bind("<Button-1>", self._on_update_click)
        self._update_url = ""

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def _add_files(self, paths):
        """Add file paths to the list."""
        file_types = self._config.get("file_types") or DEFAULT_FILE_TYPES

        for p in paths:
            if os.path.isfile(p):
                self._file_list.insert("end", p)
            elif os.path.isdir(p):
                for f in _collect_files(p, file_types):
                    self._file_list.insert("end", f)

        if self._file_list.size() > 0:
            self._drop_hint.place_forget()

    def _on_open_file(self):
        filetypes = [
            ("支援的檔案", "*.txt *.md *.docx *.xlsx *.pptx *.pdf *.jpg *.jpeg *.png *.bmp *.tiff"),
            ("文字檔", "*.txt *.md"),
            ("Office 文件", "*.docx *.xlsx *.pptx"),
            ("PDF", "*.pdf"),
            ("圖片", "*.jpg *.jpeg *.png *.bmp *.tiff"),
            ("所有檔案", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="選擇檔案", filetypes=filetypes)
        if paths:
            self._add_files(paths)

    def _on_open_folder(self):
        folder = filedialog.askdirectory(title="選擇資料夾")
        if folder:
            self._run_batch(folder)

    def _on_file_select(self, event):
        sel = self._file_list.curselection()
        if not sel:
            return
        path = self._file_list.get(sel[0])
        self._preview_file_async(path)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _on_process(self):
        """Process all files in the list."""
        if self._processing:
            return

        files = list(self._file_list.get(0, "end"))
        if not files:
            messagebox.showinfo("提示", "請先選擇要處理的檔案")
            return

        self._processing = True
        self._process_btn.configure(state="disabled")
        self._progress["value"] = 0
        self._progress["maximum"] = len(files)

        reversible = self._mode_var.get() == MODE_REVERSIBLE
        use_ner = self._ner_var.get()

        def worker():
            text_anon = Anonymizer(config=self._config, session_id="gui_session",
                                    use_ner=use_ner, reversible=reversible)
            img_anon = ImageAnonymizer(config=self._config, use_ner=use_ner)

            results = []
            for idx, fpath in enumerate(files):
                self.after(0, lambda i=idx, f=fpath: self._update_progress(i, len(files), f))

                ext = os.path.splitext(fpath)[1].lower()
                try:
                    if ext in IMAGE_EXTENSIONS:
                        out_dir = os.path.join(os.path.dirname(fpath), "anonymized_output")
                        anon_path, summary = img_anon.anonymize_image(
                            fpath, output_dir=out_dir, reversible=reversible)
                        results.append((fpath, anon_path, summary))
                    else:
                        anon_path, summary = text_anon.anonymize_file(fpath)
                        results.append((fpath, anon_path, summary))
                except Exception as e:
                    results.append((fpath, None, f"錯誤：{e}"))

            self.after(0, lambda: self._on_process_done(results))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, current: int, total: int, filename: str):
        self._progress["value"] = current + 1
        basename = os.path.basename(filename)
        self._progress_label.configure(text=f"{current + 1}/{total} {basename}")
        self._status_var.set(f"處理中：{basename}")

    def _on_process_done(self, results):
        self._processing = False
        self._process_btn.configure(state="normal")
        self._progress["value"] = self._progress["maximum"]

        pii_count = sum(1 for _, path, _ in results if path is not None)
        total = len(results)
        self._status_var.set(f"完成：{total} 個檔案已處理，{pii_count} 個發現個資")
        self._progress_label.configure(text="完成")

        summary_lines = []
        for fpath, anon_path, summary in results:
            basename = os.path.basename(fpath)
            summary_lines.append(f"  {basename}：{summary}")

        messagebox.showinfo("處理完成",
                            f"共處理 {total} 個檔案\n"
                            f"發現個資 {pii_count} 個\n\n" +
                            "\n".join(summary_lines[:20]))

    # ------------------------------------------------------------------
    # Preview (runs in background thread to avoid blocking UI)
    # ------------------------------------------------------------------

    def _preview_file_async(self, file_path: str):
        """Generate preview in a background thread."""
        ext = os.path.splitext(file_path)[1].lower()
        basename = os.path.basename(file_path)
        self._status_var.set(f"預覽中：{basename}")

        def worker():
            text_anon, img_anon = self._get_engines()
            reversible = self._mode_var.get() == MODE_REVERSIBLE

            if ext in IMAGE_EXTENSIONS:
                import tempfile
                tmpdir = tempfile.mkdtemp()
                try:
                    anon_path, _ = img_anon.anonymize_image(
                        file_path, output_dir=tmpdir, reversible=reversible)
                    self.after(0, lambda: self._preview.show_image_preview(
                        file_path, anon_path, basename))
                except Exception:
                    self.after(0, lambda: self._status_var.set("預覽失敗"))
            else:
                parser = get_parser(file_path)
                if parser is None:
                    self.after(0, lambda: self._status_var.set("不支援的檔案格式"))
                    return
                try:
                    text = parser.parse(file_path)
                except Exception:
                    self.after(0, lambda: self._status_var.set("預覽失敗"))
                    return

                anon_text, _ = text_anon.anonymize_text(text)
                self.after(0, lambda: self._preview.show_text_preview(
                    text, anon_text, basename))

            self.after(0, lambda: self._status_var.set("就緒"))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def _run_batch(self, folder: str):
        if self._processing:
            return

        output_dir = folder.rstrip(os.sep) + "_anonymized"
        confirm = messagebox.askyesno(
            "批次處理",
            f"將處理資料夾：\n{folder}\n\n"
            f"輸出至：\n{output_dir}\n\n"
            "是否繼續？"
        )
        if not confirm:
            return

        self._processing = True
        self._process_btn.configure(state="disabled")
        self._status_var.set("批次處理中...")

        reversible = self._mode_var.get() == MODE_REVERSIBLE
        use_ner = self._ner_var.get()

        def progress_cb(idx, total, fname):
            self.after(0, lambda: self._update_progress(idx, total, fname))

        def worker():
            try:
                result = run_batch(
                    folder, output_dir, self._config,
                    reversible=reversible, use_ner=use_ner,
                    progress_callback=progress_cb,
                )
                self.after(0, lambda: self._on_batch_done(result, output_dir))
            except Exception as e:
                self.after(0, lambda: self._on_batch_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_batch_done(self, result, output_dir):
        self._processing = False
        self._process_btn.configure(state="normal")
        self._status_var.set(result.summary())
        messagebox.showinfo("批次處理完成",
                            f"{result.summary()}\n\n"
                            f"輸出資料夾：{output_dir}")

    def _on_batch_error(self, error: str):
        self._processing = False
        self._process_btn.configure(state="normal")
        self._status_var.set("批次處理失敗")
        messagebox.showerror("錯誤", f"批次處理失敗：{error}")

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def _do_import_config(self, zip_path: str):
        """Import config from zip, save, and update state. Returns summary or raises."""
        config, summary = import_config(zip_path, APP_DIR)
        config["logo_templates"] = [
            os.path.join(LOGO_DIR, lt) for lt in config["logo_templates"]
        ]
        save_config(config, CONFIG_PATH)
        self._config = config
        self._invalidate_engines()
        return summary

    def _on_import_config(self):
        path = filedialog.askopenfilename(
            title="匯入設定檔",
            filetypes=[("Anonymizer 設定", "*.zip"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            summary = self._do_import_config(path)
            messagebox.showinfo("匯入成功", summary)
        except ValueError as e:
            messagebox.showerror("匯入失敗", str(e))

    def _on_export_config(self):
        path = filedialog.asksaveasfilename(
            title="匯出設定檔",
            defaultextension=".zip",
            initialfile=".anonymizer-config.zip",
            filetypes=[("Anonymizer 設定", "*.zip")],
        )
        if not path:
            return
        try:
            export_config(self._config, LOGO_DIR, path)
            messagebox.showinfo("匯出成功", f"設定已匯出至：{path}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    # ------------------------------------------------------------------
    # Auto-update check
    # ------------------------------------------------------------------

    def _check_update_async(self):
        def worker():
            has_update, version, url = check_for_update()
            if has_update:
                self.after(0, lambda: self._show_update_banner(version, url))
        threading.Thread(target=worker, daemon=True).start()

    def _show_update_banner(self, version: str, url: str):
        self._update_url = url
        self._update_label.configure(text=f"新版本 v{version} 可用（點擊下載）")
        self._update_frame.pack(side="right")

    def _on_update_click(self, event):
        if self._update_url:
            import webbrowser
            webbrowser.open(self._update_url)

    # ------------------------------------------------------------------
    # First-launch config detection
    # ------------------------------------------------------------------

    def _check_first_launch_config(self):
        if os.path.isfile(CONFIG_PATH):
            return

        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else APP_DIR
        zip_path = os.path.join(exe_dir, ".anonymizer-config.zip")
        if not os.path.isfile(zip_path):
            return

        if messagebox.askyesno("首次啟動",
                                "偵測到設定檔 (.anonymizer-config.zip)，是否匯入？"):
            try:
                summary = self._do_import_config(zip_path)
                messagebox.showinfo("匯入成功", summary)
            except ValueError as e:
                messagebox.showerror("匯入失敗", str(e))

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _on_about(self):
        from updater import __version__
        messagebox.showinfo(
            "關於",
            f"資料脫敏工具 Data Anonymizer\n"
            f"版本：{__version__}\n\n"
            "在將資料傳送給 AI 工具之前，\n"
            "先脫敏處理個人資料。\n\n"
            "支援文字、圖片、Office 文件、PDF",
        )


def main():
    logging.basicConfig(level=logging.INFO)
    app = AnonymizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
