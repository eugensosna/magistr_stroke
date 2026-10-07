#!/usr/bin/env python3
"""Перевірка посилань у тексті роботи.

    python3 tools/check.py              # звіт
    python3 tools/check.py --sort-bib   # впорядкувати список джерел за першим посиланням

Перевіряє:
  * посилання <<id>> на неіснуючі якорі та джерела;
  * джерела зі списку, на які немає посилань у тексті;
  * рисунки, таблиці, формули, лістинги (fig-, tbl-, eq-, lst-), на які немає посилань;
  * посилання на рисунок/таблицю, що стоїть після самого рисунка/таблиці (лише попередження);
  * повторювані ідентифікатори;
  * порядок джерел у списку відносно порядку першого посилання.
Код виходу 1, якщо знайдено помилки.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "thesis.adoc"

INCLUDE_RE = re.compile(r"^include::([^\[]+)\[")
XREF_RE = re.compile(r"<<([^,>]+)(?:,[^>]*)?>>|xref:([^\[]+)\[")
ANCHOR_RE = re.compile(r"\[\[([A-Za-z0-9_\-:.]+)(?:,[^\]]*)?\]\]")
BIB_RE = re.compile(r"^\*\s+\[\[\[([^\],]+)(?:,[^\]]*)?\]\]\]")
COMMENT_RE = re.compile(r"^\s*//")


def collect_lines(path, seen=None):
    """Рядки документа в порядку збирання (з урахуванням include::)."""
    seen = seen or set()
    out = []
    in_comment_block = False
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() == "////":
            in_comment_block = not in_comment_block
            continue
        if in_comment_block or COMMENT_RE.match(line):
            continue
        m = INCLUDE_RE.match(line)
        if m:
            inc = (path.parent / m.group(1)).resolve()
            if inc.suffix == ".adoc" and inc not in seen and inc.exists():
                seen.add(inc)
                out.extend(collect_lines(inc, seen))
            continue
        out.append((path, no, line))
    return out


def main():
    lines = collect_lines(MAIN)
    anchors, bib, refs = {}, {}, []
    errors, warnings = [], []

    for idx, (path, no, line) in enumerate(lines):
        where = f"{path.relative_to(ROOT)}:{no}"
        m = BIB_RE.match(line)
        if m:
            bid = m.group(1).strip()
            if bid in bib or bid in anchors:
                errors.append(f"{where}: повторюваний ідентифікатор '{bid}'")
            bib[bid] = (idx, where, path)
            line = line[m.end():]
        for a in ANCHOR_RE.finditer(line):
            aid = a.group(1)
            if aid in anchors or aid in bib:
                errors.append(f"{where}: повторюваний ідентифікатор '{aid}'")
            anchors[aid] = (idx, where)
        for r in XREF_RE.finditer(line):
            rid = (r.group(1) or r.group(2)).strip().lstrip("#")
            refs.append((rid, idx, where))

    known = set(anchors) | set(bib)
    for rid, idx, where in refs:
        if rid not in known:
            errors.append(f"{where}: посилання на невідомий ідентифікатор '{rid}'")

    referenced = {rid for rid, _, _ in refs}
    for bid, (_, where, _) in bib.items():
        if bid not in referenced:
            errors.append(f"{where}: на джерело '{bid}' немає посилань у тексті")

    for aid, (aidx, where) in anchors.items():
        if aid.split("-")[0] in ("fig", "tbl", "eq", "lst"):
            uses = [i for r, i, _ in refs if r == aid]
            if not uses:
                errors.append(f"{where}: на '{aid}' немає посилання в тексті")
            elif aid.split("-")[0] in ("fig", "tbl") and min(uses) > aidx:
                warnings.append(f"{where}: перше посилання на '{aid}' стоїть після нього")

    first_cite = {}
    for rid, idx, _ in refs:
        if rid in bib and rid not in first_cite:
            first_cite[rid] = idx
    current = sorted(bib, key=lambda b: bib[b][0])
    expected = sorted(bib, key=lambda b: first_cite.get(b, 10**9))

    if "--sort-bib" in sys.argv:
        if not bib:
            print("список джерел не знайдено")
            return 0
        path = next(iter(bib.values()))[2]
        text = path.read_text(encoding="utf-8").splitlines()
        entry_lines = {BIB_RE.match(l).group(1).strip(): l for l in text if BIB_RE.match(l)}
        positions = [i for i, l in enumerate(text) if BIB_RE.match(l)]
        ordered = [entry_lines[b] for b in expected if b in entry_lines]
        for pos, new in zip(positions, ordered):
            text[pos] = new
        path.write_text("\n".join(text) + "\n", encoding="utf-8")
        print(f"джерела у {path.relative_to(ROOT)} впорядковано за першим посиланням")
        return 0

    if current != expected:
        warnings.append("порядок джерел не відповідає порядку першого посилання "
                        "(виправити: python3 tools/check.py --sort-bib)")

    for w in warnings:
        print(f"попередження: {w}")
    for e in errors:
        print(f"помилка: {e}")
    print(f"джерел: {len(bib)}, якорів: {len(anchors)}, посилань: {len(refs)}, "
          f"помилок: {len(errors)}, попереджень: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
