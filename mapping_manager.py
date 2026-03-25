import re
import os
import json
import fcntl
import hashlib
from typing import Dict, Optional


TOKEN_PATTERN = re.compile(r'__ANON:[A-Z]+_\d+__')


class MappingManager:
    def __init__(self, session_id: str, mappings_dir: str = "/tmp/anonymizer"):
        self.session_id = session_id
        self.mappings_dir = mappings_dir
        os.makedirs(mappings_dir, exist_ok=True)

        # forward: (value, category) -> token string
        self._forward: Dict[str, str] = {}
        # reverse: token -> original value
        self._reverse: Dict[str, str] = {}
        # counters per category
        self._counters: Dict[str, int] = {}
        # file path mappings: anon_path -> original_path
        self._file_paths: Dict[str, str] = {}

    @property
    def _mapping_file(self) -> str:
        return os.path.join(self.mappings_dir, f"session_{self.session_id}.json")

    def _forward_key(self, value: str, category: str) -> str:
        return f"{category}::{value}"

    def get_or_create_token(self, value: str, category: str) -> str:
        key = self._forward_key(value, category)
        if key in self._forward:
            return self._forward[key]

        # Increment counter for this category
        count = self._counters.get(category, 0) + 1
        self._counters[category] = count

        token = f"__ANON:{category}_{count:03d}__"
        self._forward[key] = token
        self._reverse[token] = value
        return token

    def restore(self, text: str) -> str:
        def replace_token(match: re.Match) -> str:
            token = match.group(0)
            return self._reverse.get(token, token)

        return TOKEN_PATTERN.sub(replace_token, text)

    def register_file_path(self, original_path: str) -> str:
        path_hash = hashlib.sha256(original_path.encode("utf-8")).hexdigest()[:16]
        anon_path = f"/tmp/anonymizer/anonymized_{path_hash}.txt"
        self._file_paths[anon_path] = original_path
        return anon_path

    def get_original_path(self, anon_path: str) -> Optional[str]:
        return self._file_paths.get(anon_path)

    def save(self) -> None:
        data = {
            "session_id": self.session_id,
            "forward": self._forward,
            "reverse": self._reverse,
            "counters": self._counters,
            "file_paths": self._file_paths,
        }
        tmp_path = self._mapping_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self._mapping_file)

    def load(self) -> None:
        if not os.path.exists(self._mapping_file):
            return
        with open(self._mapping_file, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        self._forward = data.get("forward", {})
        self._reverse = data.get("reverse", {})
        self._counters = data.get("counters", {})
        self._file_paths = data.get("file_paths", {})

    def summary(self) -> str:
        if not self._counters:
            return "尚無脫敏資料"
        parts = []
        for category, count in sorted(self._counters.items()):
            parts.append(f"{count} 個{category}")
        return "已脫敏：" + "、".join(parts)
