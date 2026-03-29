/**
 * app.js — Frontend logic for Data Anonymizer GUI
 * Handles drag-and-drop, file upload, preview, SSE progress, and UI state.
 */

// ── PII color map ──────────────────────────────────────────────────────────
const PII_COLORS = {
    PERSON:  { bg: "#DBEAFE", color: "#3B82F6", label: "姓名" },
    PHONE:   { bg: "#FED7AA", color: "#EA580C", label: "電話" },
    EMAIL:   { bg: "#CCFBF1", color: "#0D9488", label: "Email" },
    ID:      { bg: "#FEE2E2", color: "#DC2626", label: "身分證" },
    SCHOOL:  { bg: "#EDE9FE", color: "#7C3AED", label: "學校" },
    FINANCE: { bg: "#FEF9C3", color: "#CA8A04", label: "金融" },
    URL:     { bg: "#F1F5F9", color: "#64748B", label: "URL" },
};

// ── Application state ──────────────────────────────────────────────────────
const state = {
    files: [],          // [{id, name, size}]
    mode: "reversible",
    useNer: false,
    processing: false,
    selectedFileId: null,
};

// ── Health check failure counter ───────────────────────────────────────────
let _healthFailures = 0;

// ── Utility: escape HTML ───────────────────────────────────────────────────
function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// ── Utility: format file size ──────────────────────────────────────────────
function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Dropzone init ──────────────────────────────────────────────────────────
function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");

    // Clicking the dropzone triggers the hidden file input
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragenter", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        e.stopPropagation();
        // Only remove if leaving to an element outside the dropzone
        if (!dropzone.contains(e.relatedTarget)) {
            dropzone.classList.remove("dragover");
        }
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            uploadFiles(files);
        }
    });
}

// ── Upload files ───────────────────────────────────────────────────────────
async function uploadFiles(fileList) {
    if (!fileList || fileList.length === 0) return;

    setStatus("上傳中…", "busy");

    const formData = new FormData();
    for (const f of fileList) {
        formData.append("files", f);
    }

    try {
        const resp = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            showAlert("error", err.error || "上傳失敗");
            setStatus("就緒", "idle");
            return;
        }

        const data = await resp.json();
        if (data.files && data.files.length > 0) {
            // Avoid duplicates by id
            for (const f of data.files) {
                if (!state.files.find((x) => x.id === f.id)) {
                    state.files.push(f);
                }
            }
            renderFileList();
            document.getElementById("btn-process").disabled = false;

            // Auto-preview the first newly uploaded file
            if (!state.selectedFileId && data.files.length > 0) {
                previewFile(data.files[0].id);
            }
        }

        setStatus("就緒", "idle");
    } catch (err) {
        showAlert("error", `上傳失敗：${err.message}`);
        setStatus("就緒", "idle");
    }
}

// ── Render file list ───────────────────────────────────────────────────────
function renderFileList() {
    const ul = document.getElementById("file-list");
    ul.innerHTML = "";

    for (const f of state.files) {
        const li = document.createElement("li");
        li.className = "file-item" + (f.id === state.selectedFileId ? " active" : "");
        li.dataset.fileId = f.id;

        const nameSpan = document.createElement("span");
        nameSpan.className = "file-name";
        nameSpan.textContent = f.name;
        nameSpan.title = f.name;

        const sizeSpan = document.createElement("span");
        sizeSpan.className = "file-size";
        sizeSpan.textContent = formatFileSize(f.size);

        const removeBtn = document.createElement("button");
        removeBtn.className = "file-remove";
        removeBtn.type = "button";
        removeBtn.textContent = "×";
        removeBtn.title = "移除此檔案";
        removeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            removeFile(f.id);
        });

        li.appendChild(nameSpan);
        li.appendChild(sizeSpan);
        li.appendChild(removeBtn);

        li.addEventListener("click", () => previewFile(f.id));

        ul.appendChild(li);
    }
}

// ── Remove a file from state ───────────────────────────────────────────────
function removeFile(fileId) {
    state.files = state.files.filter((f) => f.id !== fileId);

    if (state.selectedFileId === fileId) {
        state.selectedFileId = null;
        document.getElementById("content-original").innerHTML = "";
        document.getElementById("content-anonymized").innerHTML = "";
        document.getElementById("sidebar-summary").innerHTML = "";
        document.getElementById("sidebar-empty").style.display = "";
        document.getElementById("badge-original").textContent = "";
        document.getElementById("badge-anonymized").textContent = "";
    }

    renderFileList();

    if (state.files.length === 0) {
        document.getElementById("btn-process").disabled = true;
    }
}

// ── Preview a file ─────────────────────────────────────────────────────────
async function previewFile(fileId) {
    state.selectedFileId = fileId;
    renderFileList();
    setStatus("載入預覽…", "busy");

    try {
        const resp = await fetch("/api/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_id: fileId,
                mode: state.mode,
                use_ner: state.useNer,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            showAlert("error", err.error || "預覽失敗");
            setStatus("就緒", "idle");
            return;
        }

        const data = await resp.json();
        renderSidebar(data.summary || {});
        renderOriginal(data.original || "", data.spans || []);
        renderAnonymized(data.anonymized || "");
        setStatus("就緒", "idle");
    } catch (err) {
        showAlert("error", `預覽失敗：${err.message}`);
        setStatus("就緒", "idle");
    }
}

// ── Render sidebar summary ─────────────────────────────────────────────────
function renderSidebar(summary) {
    const container = document.getElementById("sidebar-summary");
    const emptyEl = document.getElementById("sidebar-empty");

    container.innerHTML = "";

    const total = Object.values(summary).reduce((a, b) => a + b, 0);

    if (total === 0) {
        emptyEl.style.display = "";
        return;
    }

    emptyEl.style.display = "none";

    for (const [category, count] of Object.entries(summary)) {
        if (count === 0) continue;

        const pii = PII_COLORS[category] || { bg: "#F3F4F6", color: "#6B7280", label: category };
        const percent = total > 0 ? Math.round((count / total) * 100) : 0;

        const itemEl = document.createElement("div");
        itemEl.className = "sidebar-item";
        itemEl.innerHTML = `
            <div class="sidebar-dot" style="background: ${pii.color}"></div>
            ${escapeHtml(pii.label)}
            <span class="sidebar-count">${count}</span>
        `;

        const barEl = document.createElement("div");
        barEl.className = "sidebar-bar";
        barEl.innerHTML = `<div class="sidebar-bar-fill" style="width: ${percent}%; background: ${pii.color}"></div>`;

        container.appendChild(itemEl);
        container.appendChild(barEl);
    }

    // Total count at the bottom
    const totalEl = document.createElement("div");
    totalEl.className = "sidebar-total";
    totalEl.textContent = `共偵測到 ${total} 筆個資`;
    container.appendChild(totalEl);
}

// ── Render original text with highlighted spans ────────────────────────────
function renderOriginal(text, spans) {
    const container = document.getElementById("content-original");
    const badgeEl = document.getElementById("badge-original");

    if (!text) {
        container.innerHTML = "";
        badgeEl.textContent = "";
        return;
    }

    // Sort spans by start position
    const sorted = [...spans].sort((a, b) => a.start - b.start);

    let html = "";
    let cursor = 0;

    for (const span of sorted) {
        if (span.start > cursor) {
            html += escapeHtml(text.slice(cursor, span.start));
        }
        const pii = PII_COLORS[span.category] || { bg: "#F3F4F6", color: "#6B7280" };
        const cls = `pii-hl-${span.category.toLowerCase()}`;
        html += `<span class="${cls}" style="background:${pii.bg};color:${pii.color};border-radius:3px;padding:0 2px;" title="${escapeHtml(span.category)}">${escapeHtml(text.slice(span.start, span.end))}</span>`;
        cursor = span.end;
    }

    if (cursor < text.length) {
        html += escapeHtml(text.slice(cursor));
    }

    container.innerHTML = `<pre style="white-space:pre-wrap;word-break:break-word;margin:0;">${html}</pre>`;
    badgeEl.textContent = spans.length > 0 ? `${spans.length} 筆` : "";
}

// ── Render anonymized text with token highlights ───────────────────────────
function renderAnonymized(text) {
    const container = document.getElementById("content-anonymized");
    const badgeEl = document.getElementById("badge-anonymized");

    if (!text) {
        container.innerHTML = "";
        badgeEl.textContent = "";
        return;
    }

    // Regex for reversible tokens: __ANON:CATEGORY_N__
    const reversibleRe = /__ANON:([A-Z]+)_\d+__/g;
    // Regex for irreversible labels: [CATEGORY] or [CATEGORY_SUBTYPE]
    const irreversibleRe = /\[([A-Z_]+)\]/g;

    // Combine both regexes by finding all matches with their positions
    const matches = [];
    let m;

    reversibleRe.lastIndex = 0;
    while ((m = reversibleRe.exec(text)) !== null) {
        matches.push({ start: m.index, end: m.index + m[0].length, full: m[0], category: m[1], type: "reversible" });
    }

    irreversibleRe.lastIndex = 0;
    while ((m = irreversibleRe.exec(text)) !== null) {
        matches.push({ start: m.index, end: m.index + m[0].length, full: m[0], category: m[1].split("_")[0], type: "irreversible" });
    }

    // Sort matches by start position, remove overlaps
    matches.sort((a, b) => a.start - b.start);

    let html = "";
    let cursor = 0;
    let tokenCount = 0;

    for (const match of matches) {
        if (match.start < cursor) continue; // skip overlapping

        if (match.start > cursor) {
            html += escapeHtml(text.slice(cursor, match.start));
        }

        const pii = PII_COLORS[match.category] || { bg: "#F3F4F6", color: "#6B7280" };
        const cls = match.type === "reversible"
            ? `token-${match.category.toLowerCase()}`
            : `label-${match.category.toLowerCase()}`;

        html += `<span class="${cls}" style="background:${pii.bg};color:${pii.color};border-radius:3px;padding:0 2px;font-family:monospace;font-size:0.9em;">${escapeHtml(match.full)}</span>`;
        cursor = match.end;
        tokenCount++;
    }

    if (cursor < text.length) {
        html += escapeHtml(text.slice(cursor));
    }

    container.innerHTML = `<pre style="white-space:pre-wrap;word-break:break-word;margin:0;">${html}</pre>`;
    badgeEl.textContent = tokenCount > 0 ? `${tokenCount} 筆` : "";
}

// ── Shared SSE stream parser ──────────────────────────────────────────────
async function readSSEStream(resp, onProgress, onDone) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data: ")) {
                try {
                    const event = JSON.parse(trimmed.slice(6));
                    if (event.type === "progress") {
                        onProgress(event);
                    } else if (event.type === "done") {
                        onDone(event);
                    }
                } catch (_) {}
            }
        }
    }
}

// ── Start processing (SSE via fetch) ──────────────────────────────────────
async function startProcessing() {
    if (state.processing || state.files.length === 0) return;

    state.processing = true;
    document.getElementById("btn-process").disabled = true;
    setStatus("準備處理…", "busy");

    const progressBar = document.getElementById("progress-bar");
    const progressFill = document.getElementById("progress-fill");
    progressFill.style.width = "0%";
    progressBar.setAttribute("aria-valuenow", "0");
    document.getElementById("sidebar-progress").style.display = "";
    document.getElementById("sidebar-download").style.display = "none";

    try {
        const resp = await fetch("/api/process", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file_ids: state.files.map((f) => f.id),
                mode: state.mode,
                use_ner: state.useNer,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            showAlert("error", err.error || "處理失敗");
            onProcessError();
            return;
        }

        await readSSEStream(
            resp,
            (event) => updateProgress(event.current, event.total, event.file),
            (event) => onProcessDone(event.results),
        );
    } catch (err) {
        showAlert("error", `處理失敗：${err.message}`);
        onProcessError();
    }
}

// ── Update progress UI ─────────────────────────────────────────────────────
function updateProgress(current, total, filename) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    const progressFill = document.getElementById("progress-fill");
    const progressBar = document.getElementById("progress-bar");
    const statusText = document.getElementById("status-text");

    progressFill.style.width = `${percent}%`;
    progressBar.setAttribute("aria-valuenow", String(percent));
    statusText.textContent = `處理中：${filename} ${current}/${total}`;
    document.getElementById("progress-label").textContent = `處理中：${filename}`;
    document.getElementById("progress-percent").textContent = `${current}/${total}`;
}

// ── On process complete ────────────────────────────────────────────────────
function onProcessDone(results) {
    state.processing = false;

    const successCount = results ? results.filter((r) => r.output !== null && !String(r.summary).startsWith("錯誤")).length : 0;
    const totalCount = results ? results.length : 0;

    showAlert("success", `處理完成！共 ${successCount}/${totalCount} 個檔案成功脫敏。`);

    setStatus("完成", "idle");
    document.getElementById("progress-fill").style.width = "100%";
    document.getElementById("progress-label").textContent = "處理完成";
    document.getElementById("progress-percent").textContent = `${successCount}/${totalCount}`;
    document.getElementById("btn-process").disabled = false;
    document.getElementById("sidebar-download").style.display = "";

    // Re-preview the selected file to show updated results
    if (state.selectedFileId) {
        previewFile(state.selectedFileId);
    }
}

// ── On process error ───────────────────────────────────────────────────────
function onProcessError() {
    state.processing = false;
    setStatus("就緒", "idle");
    document.getElementById("btn-process").disabled = false;
    document.getElementById("sidebar-progress").style.display = "none";
}

// ── Download all processed files ──────────────────────────────────────────
async function downloadAll() {
    try {
        const resp = await fetch("/api/download-all", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file_ids: state.files.map((f) => f.id) }),
        });
        if (resp.status === 204) {
            showAlert("warning", "沒有已處理的檔案可供下載");
            return;
        }
        if (!resp.ok) {
            showAlert("error", "下載失敗");
            return;
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "anonymized_output.zip";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        showAlert("error", `下載失敗：${e.message}`);
    }
}

// ── Show alert ─────────────────────────────────────────────────────────────
function showAlert(type, message) {
    const container = document.getElementById("alert-container");

    const alert = document.createElement("div");
    alert.className = `alert alert-${type}`;
    alert.setAttribute("role", "alert");

    const msgSpan = document.createElement("span");
    msgSpan.className = "alert-message";
    msgSpan.textContent = message;

    const closeBtn = document.createElement("button");
    closeBtn.className = "alert-close";
    closeBtn.type = "button";
    closeBtn.textContent = "×";
    closeBtn.setAttribute("aria-label", "關閉");
    closeBtn.addEventListener("click", () => {
        alert.remove();
    });

    alert.appendChild(msgSpan);
    alert.appendChild(closeBtn);
    container.appendChild(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// ── Set status bar ─────────────────────────────────────────────────────────
function setStatus(text, state_) {
    const statusText = document.getElementById("status-text");
    const statusDot = document.getElementById("status-dot");

    statusText.textContent = text;
    statusDot.className = "status-dot";
    if (state_ === "busy") {
        statusDot.classList.add("status-busy");
    } else if (state_ === "error") {
        statusDot.classList.add("status-error");
    } else {
        statusDot.classList.add("status-idle");
    }
}

// ── Health check ───────────────────────────────────────────────────────────
function startHealthCheck() {
    _healthFailures = 0;

    // Initial check
    checkHealth();

    setInterval(checkHealth, 30000);
}

async function checkHealth() {
    try {
        const resp = await fetch("/api/health");
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const data = await resp.json();
        _healthFailures = 0;

        const versionEl = document.getElementById("version");
        if (data.version) {
            versionEl.textContent = `v${data.version}`;
        }
    } catch (_) {
        _healthFailures++;
        if (_healthFailures >= 3) {
            showAlert("error", "伺服器已關閉，請重新啟動程式");
            setStatus("離線", "error");
        }
    }
}

// ── Init toolbar ───────────────────────────────────────────────────────────
function initToolbar() {
    const btnReversible = document.getElementById("mode-reversible");
    const btnIrreversible = document.getElementById("mode-irreversible");
    const nerCheckbox = document.getElementById("ner-checkbox");
    const btnOpenFile = document.getElementById("btn-open-file");
    const fileInput = document.getElementById("file-input");
    const btnBatch = document.getElementById("btn-batch");
    const btnProcess = document.getElementById("btn-process");

    // Mode toggle
    btnReversible.addEventListener("click", () => {
        state.mode = "reversible";
        btnReversible.classList.add("active");
        btnIrreversible.classList.remove("active");
        // Re-preview if a file is selected
        if (state.selectedFileId) {
            previewFile(state.selectedFileId);
        }
    });

    btnIrreversible.addEventListener("click", () => {
        state.mode = "irreversible";
        btnIrreversible.classList.add("active");
        btnReversible.classList.remove("active");
        // Re-preview if a file is selected
        if (state.selectedFileId) {
            previewFile(state.selectedFileId);
        }
    });

    // NER toggle
    nerCheckbox.addEventListener("change", function () {
        state.useNer = this.checked;
        // Re-preview if a file is selected
        if (state.selectedFileId) {
            previewFile(state.selectedFileId);
        }
    });

    // Open file dialog
    btnOpenFile.addEventListener("click", () => {
        fileInput.click();
    });

    // File input change
    fileInput.addEventListener("change", function () {
        if (this.files && this.files.length > 0) {
            uploadFiles(this.files);
            // Reset so the same file can be selected again
            this.value = "";
        }
    });

    // Batch processing
    btnBatch.addEventListener("click", async () => {
        const folder = prompt("請輸入資料夾路徑");
        if (!folder || !folder.trim()) return;

        setStatus("批次處理中…", "busy");
        btnBatch.disabled = true;

        try {
            const resp = await fetch("/api/batch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    folder: folder.trim(),
                    mode: state.mode,
                    use_ner: state.useNer,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                showAlert("error", err.error || "批次處理失敗");
                setStatus("就緒", "idle");
                btnBatch.disabled = false;
                return;
            }

            await readSSEStream(
                resp,
                (event) => updateProgress(event.current, event.total, event.file),
                (event) => {
                    const successCount = event.results
                        ? event.results.filter((r) => !String(r.summary).startsWith("錯誤")).length
                        : 0;
                    const totalCount = event.results ? event.results.length : 0;
                    showAlert("success", `批次處理完成！${successCount}/${totalCount} 個檔案已儲存至 ${event.output_dir}`);
                    setStatus("完成", "idle");
                    document.getElementById("progress-fill").style.width = "100%";
                },
            );
        } catch (err) {
            showAlert("error", `批次處理失敗：${err.message}`);
            setStatus("就緒", "idle");
        } finally {
            btnBatch.disabled = false;
        }
    });

    // Process button
    btnProcess.addEventListener("click", () => {
        startProcessing();
    });

    // Download all button
    document.getElementById("btn-download-all").addEventListener("click", () => {
        downloadAll();
    });
}

// ── Entry point ────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initDropzone();
    initToolbar();
    startHealthCheck();
});
