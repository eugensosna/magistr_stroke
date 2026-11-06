#!/usr/bin/env python3
"""Зауваження рецензента в тексті роботи.

Зауваження записується рядком-коментарем AsciiDoc безпосередньо перед рядком (реченням),
до якого воно стосується:

    // ЗАУВАЖЕННЯ (Коломоєць Г. П., 2026-11-05) до «RAPAEL Smart Glove»: Потрібне посилання
    // ЗАУВАЖЕННЯ [fixed] (Коломоєць Г. П., 2026-11-05) до «MusicGlove»: Потрібне посилання
    // ВІДПОВІДЬ: додано посилання на сайт виробника

  * `[fixed]` позначає виправлене зауваження;
  * необов'язковий рядок `// ВІДПОВІДЬ: ...` одразу після зауваження пояснює, що зроблено;
  * частина `до «...»` необов'язкова і потрібна лише для читача .adoc.

Рядки-коментарі не потрапляють у документ, тому release-збірка зауважень не містить.
Для dev-збірки цей скрипт копіює .adoc у build/src/, обгортає рядок після кожного зауваження
маркером <span class="review-comment"> і записує тексти зауважень у build/src/review.json.
Далі tools/filters/dstu.lua робить з маркерів примітки Word, а tools/postprocess.py
позначає виправлені примітки як закриті (resolved).

    python3 tools/review.py prepare build/src   # підготувати джерела для dev-збірки
    python3 tools/review.py list                # перелік зауважень
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ["thesis.adoc", "config", "chapters"]

COMMENT_RE = re.compile(
    r"^\s*//\s*ЗАУВАЖЕННЯ\s*(?P<fixed>\[fixed\])?\s*"
    r"\((?P<author>[^,()]+),\s*(?P<date>\d{4}-\d{2}-\d{2})\)\s*"
    r"(?:до\s+(?:«(?P<anchor>.*?)»|[^:«]*?))?\s*:\s*(?P<text>.*?)\s*$"
)
REPLY_RE = re.compile(r"^\s*//\s*ВІДПОВІДЬ\s*:\s*(?P<text>.*?)\s*$")
MARK_RE = re.compile(r"^\s*//\s*(ЗАУВАЖЕННЯ|ВІДПОВІДЬ)\b")
SKIP_RE = re.compile(r"^\s*(//.*|\[\[.*\]\]|\[.*\]|:[\w-]+:.*)?$")    # порожні, коментарі, якорі, атрибути
DELIM_RE = re.compile(r"^(\+{4,}|-{4,}|\.{4,}|={4,}|\*{4,}|_{4,}|\|===|////)\s*$")
PREFIX_RE = re.compile(r"^(=+\s+|\s*(?:\*+|-|\.+|\d+\.)\s+)")         # заголовок або пункт переліку


def parse_file(path):
    """Повертає (рядки, зауваження), де зауваження — словники з номером рядка."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    comments = []
    for no, line in enumerate(lines, 1):
        m = COMMENT_RE.match(line)
        if m:
            comments.append({
                "file": str(path.relative_to(ROOT)), "line": no,
                "author": m["author"].strip(), "date": m["date"],
                "anchor": m["anchor"] or "", "text": m["text"],
                "fixed": bool(m["fixed"]), "reply": "",
            })
        elif REPLY_RE.match(line) and comments and comments[-1]["line"] == no - 1:
            comments[-1]["reply"] = REPLY_RE.match(line)["text"]
        elif MARK_RE.match(line):
            print(f"!! {path.relative_to(ROOT)}:{no}: не вдалося розібрати зауваження: {line.strip()}",
                  file=sys.stderr)
    return lines, comments


def adoc_files():
    for item in SOURCES:
        p = ROOT / item
        yield from sorted(p.rglob("*.adoc")) if p.is_dir() else [p]


def mark(lines, comments, first_id):
    """Обгортає рядок після кожного зауваження маркером. Повертає нові рядки."""
    out = list(lines)
    by_target = {}
    for i, c in enumerate(comments):
        c["id"] = first_id + i
        t = c["line"]   # індекс наступного рядка (0-based = номер рядка зауваження)
        while t < len(out) and SKIP_RE.match(out[t]) and not DELIM_RE.match(out[t]):
            t += 1
        if t >= len(out) or DELIM_RE.match(out[t]):
            print(f"!! {c['file']}:{c['line']}: зауваження не прив'язане до тексту, пропущено",
                  file=sys.stderr)
            c["id"] = None
            continue
        by_target.setdefault(t, []).append(c["id"])
    for t, ids in by_target.items():
        body = out[t].rstrip("\n")
        m = PREFIX_RE.match(body)
        head, rest = (m.group(0), body[m.end():]) if m else ("", body)
        opens = "".join(f'pass:[<span class="review-comment" data-cid="{i}">]' for i in ids)
        out[t] = f"{head}{opens}{rest}{'pass:[</span>]' * len(ids)}\n"
    return out


def prepare(dest):
    dest = Path(dest)
    shutil.rmtree(dest, ignore_errors=True)
    allc = []
    for path in adoc_files():
        lines, comments = parse_file(path)
        new = mark(lines, comments, len(allc) + 1)
        allc.extend(comments)
        target = dest / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(new), encoding="utf-8")
    allc = [c for c in allc if c["id"] is not None]
    (dest / "review.json").write_text(json.dumps(allc, ensure_ascii=False, indent=1), encoding="utf-8")
    fixed = sum(c["fixed"] for c in allc)
    print(f">> зауважень: {len(allc)} (відкритих {len(allc) - fixed}, виправлених {fixed})")


def listing():
    total = fixed = 0
    for path in adoc_files():
        for c in parse_file(path)[1]:
            total += 1
            fixed += c["fixed"]
            state = "fixed" if c["fixed"] else "open "
            print(f"[{state}] {c['file']}:{c['line']}: {c['text']}")
    print(f"зауважень: {total} (відкритих {total - fixed}, виправлених {fixed})")


def main():
    cmd, *args = sys.argv[1:] or ["list"]
    if cmd == "prepare" and len(args) == 1:
        prepare(args[0])
    elif cmd == "list":
        listing()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
