#!/usr/bin/env python3
"""
Process AI export files (ChatGPT, Claude, etc.) and convert to NotebookLM-ready format.
Reads from EXPORT_DIR and writes to OUT_DIR.
"""

import os
import re
import sys
import json
import zipfile
import codecs
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime
import ijson

WORD = re.compile(r"\S+")
LABEL = {"user": "User", "assistant": "Assistant"}

# Get environment variables or use defaults
export_dir = Path(os.environ.get("EXPORT_DIR", os.path.expanduser("~/Downloads/AI_exports")))
out_dir = Path(os.environ.get("OUT_DIR", os.path.expanduser("~/Downloads/notebooklm_ready")))
maxw = int(os.environ.get("MAX_WORDS", "450000"))
max_mb = int(os.environ.get("MAX_MB", "5"))
maxb = max_mb * 1024 * 1024 if max_mb > 0 else 0

if not export_dir.exists():
    print("Export folder not found:", export_dir)
    sys.exit(1)

out_dir.mkdir(parents=True, exist_ok=True)

# Clean previous run outputs (prevents accidental doubling)
for old in out_dir.glob("notebooklm__part_*.md"):
    try:
        old.unlink()
    except:
        pass


def wc(s: str) -> int:
    return len(WORD.findall(s))


def bc(s: str) -> int:
    return len(s.encode("utf-8", errors="ignore"))


def would_exceed(curr_words, add_words, curr_bytes, add_bytes):
    if curr_words + add_words > maxw:
        return True
    if maxb and (curr_bytes + add_bytes > maxb):
        return True
    return False


def norm_role(x):
    if not x:
        return None
    s = str(x).strip().lower()
    if s in ("user", "human", "person", "customer"):
        return "user"
    if s in ("assistant", "ai", "model", "claude", "bot"):
        return "assistant"
    return None


def strip_bom_text(s: str) -> str:
    return s.lstrip("\ufeff")


def safe_text(s):
    if not isinstance(s, str):
        return ""
    return strip_bom_text(s).strip()


# ---------- Date helpers ----------
def date_from_epoch(ts: float):
    try:
        return datetime.fromtimestamp(float(ts)).date().isoformat()
    except Exception:
        return None


def parse_iso_date(s: str):
    # Handles ...Z, offsets, microseconds
    if not isinstance(s, str) or not s.strip():
        return None
    t = s.strip()
    try:
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        dt = datetime.fromisoformat(t)
        # localize to local clock (NotebookLM recall by date usually wants local)
        if dt.tzinfo:
            dt = dt.astimezone()
        return dt.date().isoformat()
    except Exception:
        return None


# ---------- BOM-stripping wrapper for binary JSON reads ----------
class BOMStripper:
    def __init__(self, fp):
        self.fp = fp
        self.first = True

    def read(self, n=-1):
        b = self.fp.read(n)
        if self.first:
            self.first = False
            if b.startswith(codecs.BOM_UTF8):
                b = b[len(codecs.BOM_UTF8):]
        return b

    def close(self):
        try:
            self.fp.close()
        except:
            pass


def first_non_ws_byte(path: Path, max_peek=65536):
    b = path.read_bytes()[:max_peek]
    if b.startswith(codecs.BOM_UTF8):
        b = b[len(codecs.BOM_UTF8):]
    for ch in b:
        if ch not in b" \t\r\n":
            return ch
    return None


def looks_textlike(sample: bytes) -> bool:
    if not sample:
        return False
    if sample.startswith(codecs.BOM_UTF8):
        sample = sample[len(codecs.BOM_UTF8):]
    # reject if lots of NULs (binary)
    if b"\x00" in sample:
        return False
    # printable-ish ratio
    printable = 0
    for c in sample[:4096]:
        if c in b"\t\r\n" or 32 <= c <= 126 or c >= 160:
            printable += 1
    return printable / max(1, min(len(sample), 4096)) > 0.85


def sniff_kind(path: Path):
    # returns 'json' | 'html' | 'text'
    try:
        sample = path.read_bytes()[:65536]
    except Exception:
        return None
    if not looks_textlike(sample):
        return None
    s = sample
    if s.startswith(codecs.BOM_UTF8):
        s = s[len(codecs.BOM_UTF8):]
    # find first non-ws byte
    first = None
    for ch in s:
        if ch not in b" \t\r\n":
            first = ch
            break
    if first is None:
        return "text"
    if first in (ord("["), ord("{")):
        return "json"
    if first == ord("<"):
        return "html"
    return "text"


# ---------- ChatGPT extraction ----------
def get_text_chatgpt(message: dict) -> str:
    c = message.get("content")
    if isinstance(c, dict):
        p = c.get("parts")
        if isinstance(p, list):
            out = []
            for x in p:
                if isinstance(x, str) and x.strip():
                    out.append(x.strip())
                elif isinstance(x, dict):
                    t = x.get("text")
                    if isinstance(t, str) and t.strip():
                        out.append(t.strip())
            return "\n".join(out).strip()
        t = c.get("text")
        return t.strip() if isinstance(t, str) else ""
    return c.strip() if isinstance(c, str) else ""


def extract_msgs_chatgpt(conv: dict):
    mp = conv.get("mapping")
    if not isinstance(mp, dict):
        return []
    out = []
    for node in mp.values():
        m = (node or {}).get("message")
        if not isinstance(m, dict):
            continue
        a = m.get("author")
        r = a.get("role") if isinstance(a, dict) else None
        r = norm_role(r)
        if r not in ("user", "assistant"):
            continue
        t = get_text_chatgpt(m)
        if not t:
            continue
        ts = m.get("create_time") or m.get("created_at") or 0
        try:
            ts = float(ts)
        except:
            ts = 0.0
        d = date_from_epoch(ts)
        out.append((ts, d, r, t))
    out.sort(key=lambda x: x[0])
    return out


# ---------- Claude extraction (FILTERS TOOL USE/RESULT IN ONE PASS) ----------
def extract_msgs_claude(conv: dict):
    msgs = conv.get("chat_messages")
    if not isinstance(msgs, list):
        return []
    out = []
    idx = 0
    for m in msgs:
        if not isinstance(m, dict):
            continue
        idx += 1
        r = norm_role(m.get("sender"))
        if r not in ("user", "assistant"):
            continue

        # Prefer content blocks where type == "text" (drops tool_use/tool_result entirely)
        text_parts = []
        c = m.get("content")
        if isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    t = safe_text(blk.get("text"))
                    if t:
                        text_parts.append(t)
        t = "\n".join(text_parts).strip()
        if not t:
            t = safe_text(m.get("text"))

        if not t:
            continue

        d = parse_iso_date(m.get("created_at")) or None
        # Keep stable ordering even if date missing
        ts = idx
        out.append((ts, d, r, t))
    return out


# ---------- Generic JSON extraction (best-effort) ----------
def textify(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        parts = [textify(x) for x in v]
        parts = [p for p in parts if p]
        return "\n".join(parts).strip()
    if isinstance(v, dict):
        for k in ("text", "value", "message", "content", "output", "input"):
            if k in v:
                t = textify(v.get(k))
                if t:
                    return t
        if "parts" in v:
            t = textify(v.get("parts"))
            if t:
                return t
        if "type" in v and v.get("type") == "text":
            t = v.get("text")
            if isinstance(t, str) and t.strip():
                return t.strip()
        return ""
    return ""


def find_messages_list(conv: dict):
    for k in ("messages", "chat_messages", "turns", "history", "conversation", "items"):
        v = conv.get(k)
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            return v
    for v in conv.values():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            hits = 0
            for x in v[:12]:
                if any(key in x for key in ("role", "sender", "author", "text", "content", "message", "type")):
                    hits += 1
            if hits >= 3:
                return v
    return None


def extract_msgs_generic(conv: dict):
    msgs = find_messages_list(conv)
    if not msgs:
        return []
    out = []
    idx = 0
    for m in msgs:
        idx += 1
        role = None
        if isinstance(m.get("author"), dict):
            role = norm_role(m["author"].get("role") or m["author"].get("type"))
        role = role or norm_role(m.get("role") or m.get("sender") or m.get("speaker") or m.get("type"))
        if role not in ("user", "assistant"):
            continue
        t = textify(m.get("text") or m.get("content") or m.get("message") or m)
        if not t:
            continue
        out.append((idx, None, role, t))
    return out


def extract_msgs(conv: dict):
    if isinstance(conv.get("mapping"), dict):
        msgs = extract_msgs_chatgpt(conv)
        if msgs:
            return msgs
    if isinstance(conv.get("chat_messages"), list):
        msgs = extract_msgs_claude(conv)
        if msgs:
            return msgs
    return extract_msgs_generic(conv)


def iter_conversations(path: Path):
    first = first_non_ws_byte(path)
    if first is None:
        return
    # Stream arrays: [ ... ]
    if first == ord("["):
        with path.open("rb") as raw:
            fp = BOMStripper(raw)
            for item in ijson.items(fp, "item"):
                if isinstance(item, dict):
                    yield item
        return
    # Stream known object keys
    if first == ord("{"):
        for prefix in ("conversations.item", "chats.item", "data.item", "items.item"):
            try:
                with path.open("rb") as raw:
                    fp = BOMStripper(raw)
                    it = ijson.items(fp, prefix)
                    first_item = next(it, None)
                    if isinstance(first_item, dict):
                        yield first_item
                        for item in it:
                            if isinstance(item, dict):
                                yield item
                        return
            except Exception:
                continue
        # Fallback: load as normal JSON
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            txt = strip_bom_text(txt)
            obj = json.loads(txt)
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        yield item
            elif isinstance(obj, dict):
                yield obj
        except Exception:
            return


# ---------- HTML -> text (streaming) ----------
BLOCK_TAGS = {
    "p", "br", "div", "li", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "main",
    "ul", "ol"
}
IGNORE_TAGS = {"script", "style", "noscript"}


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignore_depth = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in IGNORE_TAGS:
            if self.ignore_depth > 0:
                self.ignore_depth -= 1
            return
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if self.ignore_depth > 0:
            return
        t = data.strip()
        if t:
            self.out.append(t + " ")

    def drain(self):
        if not self.out:
            return ""
        s = "".join(self.out)
        self.out = []
        return s


def normalize_text(s: str) -> str:
    s = strip_bom_text(s)
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


DATE_PATTERNS = [
    ("%B %d, %Y", re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4}$")),   # January 20, 2026
    ("%b %d, %Y", re.compile(r"^[A-Za-z]{3} \d{1,2}, \d{4}$")),  # Jan 20, 2026
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),           # 2026-01-20
]


def detect_date_heading(s: str):
    t = normalize_text(s)
    if not t:
        return None
    t1 = t.strip()
    for fmt, rx in DATE_PATTERNS:
        if rx.match(t1):
            try:
                return datetime.strptime(t1, fmt).date().isoformat()
            except Exception:
                continue
    return None


def iter_html_paragraphs_stream(byte_stream):
    parser = HTMLTextExtractor()
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buf = ""
    for chunk in byte_stream:
        parser.feed(decoder.decode(chunk))
        buf += parser.drain()
        buf = normalize_text(buf)
        while "\n\n" in buf:
            para, buf = buf.split("\n\n", 1)
            para = normalize_text(para)
            if para:
                yield para
    parser.close()
    buf += parser.drain()
    buf = normalize_text(buf)
    if buf:
        for p in re.split(r"\n\s*\n", buf):
            p = normalize_text(p)
            if p:
                yield p


def iter_html_paragraphs_file(path: Path, chunk_size=1024*1024):
    with path.open("rb") as fp:
        def gen():
            while True:
                b = fp.read(chunk_size)
                if not b:
                    break
                yield b
        yield from iter_html_paragraphs_stream(gen())


# ---------- ZIP: auto-find MyActivity.* ----------
def pick_best_myactivity_member(names):
    def score(n):
        ln = n.lower()
        s = 0
        if "myactivity" in ln:
            s += 25
        if "my activity" in ln:
            s += 10
        if "gemini" in ln or "bard" in ln:
            s += 10
        if ln.endswith(".html"):
            s += 3
        if ln.endswith(".json"):
            s += 2
        return s
    scored = sorted(names, key=lambda n: (score(n), -len(n)), reverse=True)
    for n in scored:
        if "myactivity" in n.lower() and score(n) >= 25:
            return n
    return None


def iter_zip_myactivity(zip_path: Path):
    with zipfile.ZipFile(zip_path, "r") as z:
        member = pick_best_myactivity_member(z.namelist())
        if not member:
            return None, None, None
        name = Path(member).name.lower()

        if name.endswith(".html"):
            fp = z.open(member, "r")
            def gen():
                with fp:
                    while True:
                        b = fp.read(1024*1024)
                        if not b:
                            break
                        yield b
            return member, "html", iter_html_paragraphs_stream(gen())

        if name.endswith(".json"):
            raw = z.read(member)
            try:
                obj = json.loads(raw.decode("utf-8", errors="ignore").lstrip("\ufeff"))
            except Exception:
                obj = None
            if obj is None:
                return member, "text", iter(["(Could not parse MyActivity.json)"])
            # Dump as text (best-effort)
            return member, "text", iter([json.dumps(obj, ensure_ascii=False)])

    return None, None, None


# ---------- Discovery (includes extensionless text-like files) ----------
SUPPORTED_EXTS = {".json", ".jsonl", ".html", ".htm", ".zip", ".txt", ".md"}
EXCLUDE_NAMES = {"manifest.json", "settings.json"}


def is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def discover_inputs(root: Path, out_dir: Path):
    files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.lower() in EXCLUDE_NAMES:
            continue
        if is_under(p, out_dir):
            continue

        suf = p.suffix.lower()
        if suf in SUPPORTED_EXTS:
            files.append(p)
            continue

        # extensionless: include if it looks like text/JSON/HTML
        if suf == "":
            try:
                sample = p.read_bytes()[:65536]
            except Exception:
                continue
            if looks_textlike(sample):
                files.append(p)
    return files


def score_input(p: Path) -> int:
    n = p.name.lower()
    s = 0
    if n == "conversations.json":
        s += 1000000
    if n in ("myactivity.html", "myactivity.htm", "myactivity.json"):
        s += 900000
    if p.suffix.lower() == ".zip":
        s += 800000
    if p.suffix.lower() in (".html", ".htm"):
        s += 700000
    if p.suffix.lower() in (".json", ".jsonl") or sniff_kind(p) == "json":
        s += 600000
    try:
        s += int(p.stat().st_mtime)
    except:
        pass
    return s


cand = discover_inputs(export_dir, out_dir)
if not cand:
    print("No supported files found in:", export_dir)
    sys.exit(1)
cand = sorted(cand, key=score_input, reverse=True)

# ---------- Writer / chunking ----------
part = 1
words = 0
bytes_ = 0
f = None
files_written = 0


def new_file():
    global part, words, bytes_, f, files_written
    if f:
        f.close()
    f = (out_dir / f"notebooklm__part_{part:04d}.md").open("w", encoding="utf-8", newline="\n")
    files_written += 1
    part += 1
    words = 0
    bytes_ = 0


def write_block(block: str):
    global words, bytes_
    w = wc(block)
    b = bc(block)
    if would_exceed(words, w, bytes_, b):
        new_file()
    f.write(block)
    words += w
    bytes_ += b


def write_date_delim(d: str):
    write_block(f"\n---\n## DATE: {d}\n---\n\n")


new_file()

conv_count = 0
msg_count = 0
conv_zero = 0

for inp in cand:
    kind = sniff_kind(inp)

    # ZIP: best MyActivity.* inside, chunk with date headings
    if inp.suffix.lower() == ".zip":
        member, k2, it = iter_zip_myactivity(inp)
        if not member or it is None:
            continue
        conv_count += 1
        write_block(f"# Takeout ZIP → {Path(member).name}\n\n")
        current_date = None
        for para in it:
            d = detect_date_heading(para)
            if d and d != current_date:
                current_date = d
                write_date_delim(current_date)
                continue
            msg_count += 1
            write_block(f"{para}\n\n")
        write_block("\n")
        continue

    # HTML: chunk with date headings
    if kind == "html" or inp.suffix.lower() in (".html", ".htm"):
        conv_count += 1
        write_block(f"# {inp.name}\n\n")
        current_date = None
        for para in iter_html_paragraphs_file(inp):
            d = detect_date_heading(para)
            if d and d != current_date:
                current_date = d
                write_date_delim(current_date)
                continue
            msg_count += 1
            write_block(f"{para}\n\n")
        write_block("\n")
        continue

    # TEXT/MD: raw chunking
    if kind == "text" and inp.suffix.lower() in (".txt", ".md", ""):
        conv_count += 1
        write_block(f"# {inp.name}\n\n")
        try:
            text = normalize_text(inp.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        current_date = None
        for para in re.split(r"\n\s*\n", text):
            p = normalize_text(para)
            if not p:
                continue
            d = detect_date_heading(p)
            if d and d != current_date:
                current_date = d
                write_date_delim(current_date)
                continue
            msg_count += 1
            write_block(p + "\n\n")
        write_block("\n")
        continue

    # JSON/JSONL: ChatGPT / Claude / generic
    if kind == "json" or inp.suffix.lower() in (".json", ".jsonl"):
        any_conv = False
        for conv in iter_conversations(inp):
            any_conv = True
            conv_count += 1

            title = conv.get("title") or conv.get("name") or conv.get("conversation_name") or inp.name or "Untitled Conversation"
            title = safe_text(title) or "Untitled Conversation"
            write_block(f"# {title}\n\n")

            msgs = extract_msgs(conv)
            if not msgs:
                conv_zero += 1

            current_date = None
            for _, d, r, t in msgs:
                if d and d != current_date:
                    current_date = d
                    write_date_delim(current_date)
                msg_count += 1
                write_block(f"**{LABEL.get(r, r)}:**\n\n{normalize_text(t)}\n\n")

            write_block("\n")

        if not any_conv:
            continue

if f:
    f.close()

print("Done.")
print("Export dir:", export_dir)
print("Inputs considered:", len(cand))
print("Conversations/logs:", conv_count)
print("Blocks extracted:", msg_count)
print("Conversations with 0 messages:", conv_zero)
print("Output files:", files_written)
print("Output dir:", out_dir)
print("Max words/file:", maxw)
if maxb:
    print("Max file size:", max_mb, "MB")
