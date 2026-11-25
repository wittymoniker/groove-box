"""document_io.py — read/write session documents, lyrics, notes (text/markdown/MGR blob)."""
from __future__ import annotations
import os, json, time
from pathlib import Path
from typing import Optional

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_text(path: str, text: str) -> str:
    path = str(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return path

def read_markdown(path: str) -> dict:
    body = read_text(path)
    title = Path(path).stem
    if body.startswith("# "):
        title = body.splitlines()[0][2:].strip() or title
    return {"title": title, "body": body, "path": path}

def write_session_doc(path: str, title: str, body: str, meta: Optional[dict] = None) -> str:
    meta = dict(meta or {})
    meta.update({"title": title, "ts": time.time(), "app": "MathematiciansGroovebox"})
    if str(path).lower().endswith(".mgr") or ".mgr." in str(path).lower():
        try:
            import mgr_format as mgr
            payload = json.dumps({"meta": meta, "body": body}, ensure_ascii=False).encode("utf-8")
            with open(path, "wb") as f:
                mgr.write_header(f, mgr.TYPE["project_blob"], meta)
                f.write(payload)
            # readable sibling
            write_text(path + ".md", f"# {title}\n\n{body}\n")
            return path
        except Exception:
            pass
    md = f"---\n{json.dumps(meta)}\n---\n\n# {title}\n\n{body}\n"
    return write_text(path if path.endswith((".md", ".txt")) else path + ".md", md)
