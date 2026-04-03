#!/usr/bin/env python3
"""Interactive setup wizard for the anonymizer."""
import json
import os
import sys
import stat

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LEARNED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned_terms.json")
MAPPINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mappings")

def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    result = input(f"{prompt}{suffix}: ").strip()
    return result if result else default

def ask_list(prompt):
    result = input(f"{prompt}: ").strip()
    if not result:
        return []
    return [item.strip() for item in result.split(",") if item.strip()]

def main():
    print("\n歡迎使用脫敏引擎初始化工具！\n")
    config = {
        "version": 1,
        "auto_detect": True,
        "sensitivity": "ask_uncertain",
        "custom_terms": {},
        "substring_match": True,
        "scan_paths": [],
        "file_types": [".docx", ".xlsx", ".pptx", ".pdf", ".md", ".csv", ".json", ".txt", ".html", ".xml"],
        "logo_templates": [],
        "persist_mapping": False,
        "max_file_pages": 50,
        "hook_timeout_seconds": 120,
    }

    school_full = ask("請輸入您的學校全名")
    school_short = ask_list("常見簡稱（逗號分隔）")
    school_en = ask("英文名稱")
    schools = [s for s in [school_full] + school_short + [school_en] if s]
    if schools:
        config["custom_terms"]["schools"] = schools

    colleges = ask_list("需要加入的學院名稱（逗號分隔，留空跳過）")
    if colleges:
        config["custom_terms"]["colleges"] = colleges

    depts = ask_list("需要加入的學系（逗號分隔）")
    if depts:
        config["custom_terms"]["departments"] = depts

    insts = ask_list("需要加入的研究所（逗號分隔）")
    if insts:
        config["custom_terms"]["institutes"] = insts

    locs = ask_list("需要加入的地理位置（逗號分隔）")
    if locs:
        config["custom_terms"]["locations"] = locs

    docs = ask_list("需要加入的內部文件名稱（逗號分隔）")
    if docs:
        config["custom_terms"]["documents"] = docs

    paths = ask_list("需要自動掃描的資料夾路徑（逗號分隔）")
    config["scan_paths"] = paths

    ft_input = ask("需要掃描的副檔名", ",".join(config["file_types"]))
    config["file_types"] = [f.strip() if f.strip().startswith('.') else f'.{f.strip()}' for f in ft_input.split(",")]

    persist = ask("是否啟用跨會話持久化 mapping？(y/N)", "N")
    config["persist_mapping"] = persist.lower() == 'y'

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    if not os.path.exists(LEARNED_PATH):
        with open(LEARNED_PATH, 'w') as f:
            json.dump({"confirmed_sensitive": [], "confirmed_safe": []}, f)

    os.makedirs(MAPPINGS_DIR, exist_ok=True)

    if sys.platform != "win32":
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(LEARNED_PATH, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(MAPPINGS_DIR, stat.S_IRWXU)

    print(f"\n✅ 設定已存到 {CONFIG_PATH}")
    print("✅ 檔案權限已設定 (chmod 600/700)")

    print("\n正在載入 ckip-transformers 模型...")
    try:
        from ckip_transformers.nlp import CkipNerChunker
        CkipNerChunker(model="bert-base")
        print("✅ 模型載入完成")
    except Exception as e:
        print(f"⚠️ 模型載入失敗: {e}")

if __name__ == "__main__":
    main()
